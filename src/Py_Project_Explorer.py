import sys
import os
import shutil
import zipfile
import subprocess
import venv
import markdown2
import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeView, QFileSystemModel, QVBoxLayout,
                             QWidget, QTextEdit, QPushButton, QHBoxLayout, QLabel, QFileDialog,
                             QMessageBox, QMenu, QAction, QInputDialog, QSplitter, QLineEdit,
                             QPlainTextEdit)
from PyQt5.QtCore import Qt, QDir, QUrl, QProcess, QObject, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView


# --- Pygments for Syntax Highlighting ---
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatter import Formatter

# Helper class to bridge Pygments and QSyntaxHighlighter
class QFormatter(Formatter):
    def __init__(self):
        super().__init__()
        self.data = []

    def format(self, tokensource, outfile):
        self.data = []
        for ttype, value in tokensource:
            self.data.append((ttype, value))

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.formatter = QFormatter()
        self.lexer = PythonLexer()

        # Define styles for different token types (Monokai-inspired dark theme)
        self.styles = {
            'Token.Keyword': self.create_format(QColor("#F92672")),
            'Token.Name.Function': self.create_format(QColor("#A6E22E")),
            'Token.Name.Class': self.create_format(QColor("#A6E22E"), bold=True),
            'Token.String': self.create_format(QColor("#E6DB74")),
            'Token.Comment': self.create_format(QColor("#75715E"), italic=True),
            'Token.Operator': self.create_format(QColor("#F92672")),
            'Token.Number': self.create_format(QColor("#AE81FF")),
            'Token.Keyword.Constant': self.create_format(QColor("#AE81FF")),
            'Token.Name.Builtin': self.create_format(QColor("#66D9EF"), italic=True),
        }

    def create_format(self, color, bold=False, italic=False):
        """Creates a QTextCharFormat for a specific style."""
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if bold:
            fmt.setFontWeight(QFont.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def highlightBlock(self, text):
        """Highlights a block of text using Pygments."""
        highlight(text, self.lexer, self.formatter)
        
        start_index = 0
        for ttype, value in self.formatter.data:
            length = len(value)
            while ttype not in self.styles and ttype.parent:
                ttype = ttype.parent
            
            if ttype in self.styles:
                self.setFormat(start_index, length, self.styles[ttype])
            start_index += length

class SearchWorker(QObject):
    """A worker that searches files in the background."""
    finished = pyqtSignal(list)

    def __init__(self, root_path, search_text):
        super().__init__()
        self.root_path = root_path
        self.search_text = search_text

    def run(self):
        """Performs the long-running search task."""
        matches = []
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if file.endswith(('.py', '.txt', '.md', '.markdown', '.ini', '.json')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            if self.search_text in f.read().lower():
                                # *** THE FIX IS HERE: Use basename for the filter ***
                                matches.append(os.path.basename(file_path))
                    except Exception:
                        continue
        self.finished.emit(matches)

# --- Main Application ---
class PythonProjectExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyCentric Project Explorer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize variables
        self.current_file_path = None
        self.venv_path = None
        self.showing_preview = False

        # Setup QProcess for real-time script execution
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.on_process_finished)
        
        # Setup search thread and timer
        self.search_thread = None
        self.search_worker = None
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(500)
        self.search_timer.timeout.connect(self.start_search_thread)
        
        # Setup UI
        self.setup_ui()
        
        # Set initial project directory
        current_dir = os.getcwd()
        self.model.setRootPath(current_dir)
        self.tree.setRootIndex(self.model.index(current_dir))
        self.file_info.setText(f"Current project folder: {current_dir}")
        self.check_venv()

    def setup_ui(self):    
        self.statusBar()
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)
        
        # --- Left Panel ---
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files by content...")
        self.search_bar.textChanged.connect(self.search_files)
        
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self.model.setNameFilters(["*.py", "*.txt", "*.md", "*.markdown", "*.ini", "*.json", "*.zip", "requirements.txt"])
        self.model.setNameFilterDisables(False)
        
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setColumnWidth(0, 250)
        self.tree.clicked.connect(self.on_tree_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        
        btn_select_folder = QPushButton("Select Project Folder")
        btn_select_folder.clicked.connect(self.select_project_folder)
        
        left_layout.addWidget(btn_select_folder)
        left_layout.addWidget(self.search_bar)
        left_layout.addWidget(self.tree)
        left_widget.setLayout(left_layout)
        
        # --- Right Panel ---
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        self.file_info = QLabel("Select a file to view details")
        self.file_info.setWordWrap(True)
        
        self.editor_splitter = QSplitter(Qt.Vertical)
        
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setStyleSheet("background-color: #272822; color: #F8F8F2;")
        self.highlighter = PythonHighlighter(self.editor.document())
        
        self.preview_frame = QWebEngineView()
        self.preview_frame.setVisible(False)
        
        self.editor_splitter.addWidget(self.editor)
        self.editor_splitter.addWidget(self.preview_frame)
        self.editor_splitter.setSizes([600, 200])
        
        self.output = QTextEdit()
        self.output.setFont(QFont("Courier New", 10))
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(200)
        
        button_layout = QHBoxLayout()
        btn_save = QPushButton("Save File")
        btn_save.clicked.connect(self.save_file)
        btn_run = QPushButton("Run Python File")
        btn_run.clicked.connect(self.run_python_file)
        btn_lint = QPushButton("Lint with flake8")
        btn_lint.clicked.connect(self.lint_python_file)
        btn_create_venv = QPushButton("Create Virtual Env")
        btn_create_venv.clicked.connect(self.create_venv)
        btn_toggle_preview = QPushButton("Toggle Markdown Preview")
        btn_toggle_preview.clicked.connect(self.toggle_preview)
        
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_run)
        button_layout.addWidget(btn_lint)
        button_layout.addWidget(btn_create_venv)
        button_layout.addWidget(btn_toggle_preview)
        
        right_layout.addWidget(self.file_info)
        right_layout.addWidget(self.editor_splitter)
        right_layout.addWidget(self.output)
        right_layout.addLayout(button_layout)
        right_widget.setLayout(right_layout)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])
        
    def select_project_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder", os.getcwd())
        if folder:
            self.model.setRootPath(folder)
            self.tree.setRootIndex(self.model.index(folder))
            self.file_info.setText("Selected project folder: " + folder)
            self.editor.clear()
            self.output.clear()
            self.preview_frame.setHtml("")
            self.preview_frame.setVisible(False)
            self.showing_preview = False
            self.venv_path = None
            self.check_venv()
            
    def check_venv(self):
        venv_dirs = ['venv', '.venv']
        root = self.model.rootPath()
        for venv_dir in venv_dirs:
            path = os.path.join(root, venv_dir)
            if os.path.isdir(path):
                self.venv_path = path
                self.output.append(f"✅ Virtual environment found: {path}")
                break
        else:
            self.venv_path = None
            
    def on_tree_clicked(self, index):
        path = self.model.filePath(index)
        if os.path.isfile(path):
            self.current_file_path = path
            self.update_file_info(path)
            if path.endswith(('.py', '.txt', '.md', '.markdown', '.ini', '.json', 'requirements.txt')):
                self.load_file_content(path)
                if path.endswith(('.md', '.markdown')) and self.showing_preview:
                    self.load_markdown_preview(path)
            else:
                self.editor.setPlainText("Binary or unsupported file.\nCannot display content.")
                self.editor.setReadOnly(True)
        else:
            self.current_file_path = None
            self.editor.clear()
            self.update_file_info(path)
            
    def update_file_info(self, path):
        info = []
        if os.path.exists(path):
            file_info = os.stat(path)
            info.append(f"Path: {path}")
            info.append(f"Size: {file_info.st_size / 1024:.2f} KB")
            info.append(f"Modified: {datetime.datetime.fromtimestamp(file_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        self.file_info.setText("\n".join(info))
        
    def load_file_content(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.editor.setPlainText(content)
                self.editor.setReadOnly(False)
        except Exception as e:
            self.editor.setPlainText(f"Error loading file: {str(e)}")
            self.editor.setReadOnly(True)
            
    def load_markdown_preview(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = markdown2.markdown(f.read(), extras=["fenced-code-blocks", "codehilite", "tables"])
                self.preview_frame.setHtml(html_content)
                self.preview_frame.setVisible(True)
        except Exception as e:
            self.preview_frame.setHtml(f"<h3>Error</h3><p>Could not load file: {str(e)}</p>")
            self.preview_frame.setVisible(True)
            
    def toggle_preview(self):
        if not self.current_file_path or not self.current_file_path.endswith(('.md', '.markdown')):
            QMessageBox.information(self, "Info", "Preview is only for Markdown (.md, .markdown) files.")
            return
        self.showing_preview = not self.showing_preview
        if self.showing_preview:
            self.load_markdown_preview(self.current_file_path)
            self.editor_splitter.setSizes([400, 400])
        else:
            self.preview_frame.setHtml("")
            self.preview_frame.setVisible(False)
            self.editor_splitter.setSizes([800, 0])
            
    def save_file(self):
        if self.current_file_path and not self.editor.isReadOnly():
            try:
                with open(self.current_file_path, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
                if self.current_file_path.endswith(('.md', '.markdown')) and self.showing_preview:
                    self.load_markdown_preview(self.current_file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
                
    def run_python_file(self):
        if not self.current_file_path or not self.current_file_path.endswith('.py'):
            QMessageBox.critical(self, "Error", "Please select a Python (.py) file to run.")
            return
        if self.process.state() == QProcess.Running:
            QMessageBox.information(self, "Info", "A process is already running.")
            return
        self.output.clear()
        self.output.append(f"--- Running {os.path.basename(self.current_file_path)} ---")
        python_cmd = sys.executable
        if self.venv_path:
            python_cmd = os.path.join(self.venv_path, "Scripts" if sys.platform == "win32" else "bin", "python")
        self.process.start(python_cmd, [self.current_file_path])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode(errors='ignore')
        self.output.insertPlainText(data)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode(errors='ignore')
        self.output.insertPlainText(f"ERROR: {data}")

    def on_process_finished(self):
        self.output.append("\n--- Script finished ---")

    def lint_python_file(self):
        if not self.current_file_path or not self.current_file_path.endswith('.py'):
            QMessageBox.critical(self, "Error", "Please select a Python (.py) file to lint.")
            return
        self.output.clear()
        self.output.append("--- Running flake8 ---")
        try:
            python_cmd = sys.executable
            if self.venv_path:
                python_cmd = os.path.join(self.venv_path, "Scripts" if sys.platform == "win32" else "bin", "python")
            result = subprocess.run([python_cmd, "-m", "flake8", self.current_file_path], capture_output=True, text=True, timeout=15)
            self.output.append(result.stdout if result.stdout else "✅ No issues found.")
        except Exception as e:
            self.output.append(f"Error running flake8: {str(e)}")

    def create_venv(self):
        venv_dir = os.path.join(self.model.rootPath(), "venv")
        if os.path.exists(venv_dir):
            QMessageBox.warning(self, "Exists", "A 'venv' folder already exists.")
            return
        try:
            venv.create(venv_dir, with_pip=True)
            self.venv_path = venv_dir
            self.check_venv()
            QMessageBox.information(self, "Success", f"Virtual environment created at: {venv_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create virtual environment: {str(e)}")

    def search_files(self):
        """Triggers the search timer when text changes."""
        self.search_timer.start()
            
    def start_search_thread(self):
        """Sets up and starts the background search worker."""
        if self.search_thread and self.search_thread.isRunning():
            return
        search_text = self.search_bar.text().strip().lower()
        if not search_text:
            self.model.setNameFilters(["*.py", "*.txt", "*.md", "*.markdown", "*.ini", "*.json", "*.zip", "requirements.txt"])
            self.model.setNameFilterDisables(False)
            return
        self.statusBar().showMessage("Searching...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.search_thread = QThread()
        self.search_worker = SearchWorker(self.model.rootPath(), search_text)
        self.search_worker.moveToThread(self.search_thread)
        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.finished.connect(self.update_search_results)
        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.finished.connect(self.search_worker.deleteLater)
        self.search_thread.finished.connect(self.search_thread.deleteLater)
        self.search_thread.finished.connect(self.on_search_thread_finished)
        self.search_thread.start()

    def update_search_results(self, matches):
        """Updates the file tree filter with the search results."""
        if matches:
            self.model.setNameFilters(matches)
        else:
            self.model.setNameFilters(["*.nomatch"])
        self.model.setNameFilterDisables(False)
        self.statusBar().clearMessage()
        QApplication.restoreOverrideCursor()    

    def on_search_thread_finished(self):
        """Clears the reference to the finished search thread."""
        self.search_thread = None

    def open_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid(): return
        path = self.model.filePath(index)
        menu = QMenu()
        if os.path.isdir(path):
            menu.addAction("New File...", lambda: self.create_new_file(path))
            menu.addAction("New Folder...", lambda: self.create_new_folder(path))
            menu.addSeparator()
            menu.addAction("Zip Folder", lambda: self.zip_item(path))
        else:
            if path.endswith('.py'):
                menu.addAction("Run Python File", self.run_python_file)
                menu.addAction("Lint with flake8", self.lint_python_file)
            if path.endswith(('.md', '.markdown')):
                menu.addAction("Toggle Markdown Preview", self.toggle_preview)
            if path.endswith('.zip'):
                menu.addAction("Unzip File", lambda: self.unzip_file(path))
            else:
                menu.addAction("Zip File", lambda: self.zip_item(path))
            if path.endswith('requirements.txt'):
                 menu.addAction("Install Dependencies", lambda: self.install_requirements(path))
        menu.addSeparator()
        menu.addAction("Copy Path", lambda: QApplication.clipboard().setText(path))
        menu.addAction("Delete", lambda: self.delete_item(path))
        menu.exec_(self.tree.viewport().mapToGlobal(position))
        
    def install_requirements(self, path):
        if not self.venv_path:
            QMessageBox.critical(self, "Error", "No virtual environment found or selected.")
            return
        self.output.clear()
        self.output.append(f"--- Installing from {os.path.basename(path)} ---")
        pip_cmd = os.path.join(self.venv_path, "Scripts" if sys.platform == "win32" else "bin", "pip")
        self.process.start(pip_cmd, ["install", "-r", path])

    def create_new_file(self, folder_path):
        file_name, ok = QInputDialog.getText(self, "New File", "Enter file name:")
        if ok and file_name:
            new_path = os.path.join(folder_path, file_name)
            try:
                with open(new_path, 'w', encoding='utf-8') as f:
                    f.write(f"# New file: {file_name}\n")
                QMessageBox.information(self, "Success", f"Created {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create file: {str(e)}")
                
    def create_new_folder(self, folder_path):
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            new_path = os.path.join(folder_path, folder_name)
            try:
                os.makedirs(new_path, exist_ok=True)
                QMessageBox.information(self, "Success", f"Created {folder_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create folder: {str(e)}")
                
    def delete_item(self, path):
        reply = QMessageBox.question(self, "Delete", f"Are you sure you want to delete {os.path.basename(path)}?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if os.path.isfile(path): os.remove(path)
                else: shutil.rmtree(path)
                self.editor.clear()
                self.preview_frame.setHtml("")
                self.preview_frame.setVisible(False)
                self.file_info.setText("Select a file to view details")
                QMessageBox.information(self, "Success", "Item deleted successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {str(e)}")
    
    def get_unique_path(self, path):
        base, ext = os.path.splitext(path)
        counter = 1
        new_path = path
        while os.path.exists(new_path):
            new_path = f"{base}_{counter}{ext}"
            counter += 1
        return new_path

    def zip_item(self, path):
        base_name = os.path.splitext(path)[0] if os.path.isfile(path) else path
        zip_path = self.get_unique_path(base_name + ".zip")
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.isfile(path):
                    zipf.write(path, os.path.basename(path))
                else:
                    for root, _, files in os.walk(path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(path))
                            zipf.write(file_path, arcname)
            QMessageBox.information(self, "Success", f"Created archive: {os.path.basename(zip_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to zip: {str(e)}")
            
    def unzip_file(self, path):
        if not path.endswith('.zip'):
            QMessageBox.critical(self, "Error", "Selected file is not a zip file")
            return
        extract_dir = os.path.splitext(path)[0]
        extract_dir = self.get_unique_path(extract_dir)
        try:
            with zipfile.ZipFile(path, 'r') as zipf:
                zipf.extractall(extract_dir)
            QMessageBox.information(self, "Success", f"Extracted to: {extract_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to unzip: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = PythonProjectExplorer()
    window.show()
    sys.exit(app.exec_())