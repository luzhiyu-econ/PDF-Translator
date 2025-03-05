import os
import sys
import subprocess
import json
import re
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                            QFileDialog, QComboBox, QLineEdit, QProgressBar, 
                            QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
                            QGridLayout, QCheckBox, QSpinBox, QTextEdit, 
                            QGroupBox, QFormLayout, QDialogButtonBox, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QFont, QTextCursor
import sys
import os

# 翻译服务配置
TRANSLATION_SERVICES = {
    "Google (默认)": "google",
    "Bing": "bing",
    "DeepL": "deepl",
    "OpenAI": "openai",
    "Azure OpenAI": "azure-openai",
    "智谱 AI": "zhipu",
    "魔搭 ModelScope": "modelscope",
    "Ollama (本地模型)": "ollama",
    "Xinference (本地模型)": "xinference",
    "Gemini": "gemini",
    "DeepSeek": "deepseek",
    "阿里千问翻译": "qwen-mt",
    "硅基流动": "silicon",  # 新增 Silicon 服务
    "腾讯云翻译": "tencent"  # 新增 腾讯云翻译 服务
}

# 模型配置
MODEL_OPTIONS = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    "azure-openai": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    "zhipu": ["glm-4-flash", "glm-4", "glm-3-turbo"],
    "modelscope": ["Qwen/Qwen2.5-Coder-32B-Instruct", "Qwen/Qwen2.5-7B-Instruct"],
    "ollama": ["gemma2", "llama3", "mixtral"],
    "xinference": ["gemma-2-it", "llama3", "qwen2"],
    "gemini": ["gemini-1.5-flash", "gemini-1.5-pro"],
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "qwen-mt": ["qwen-mt-turbo"],
    "silicon": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-7B-Instruct"],  # 新增 Silicon 模型选项
    "tencent": []  # 腾讯云翻译不需要选择模型
}

# 语言映射
LANGUAGES = {
    "英语": "en", 
    "中文(简体)": "zh-CN",
    "中文(繁体)": "zh-TW",
    "日语": "ja",
    "韩语": "ko",
    "法语": "fr",
    "德语": "de",
    "西班牙语": "es",
    "俄语": "ru"
}
# 设置编码
if sys.stdout.encoding != 'utf-8':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    elif hasattr(sys.stdout, 'buffer'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ['PYTHONIOENCODING'] = 'utf-8'

class TranslationThread(QThread):
    progress_signal = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)  # 当前页数，总页数
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, params):
        super().__init__()
        self.params = params
        self.process = None
        
    def run(self):
        try:
            command = ["pdf2zh"]
            
            # 文件或URL
            if self.params["file_path"]:
                command.append(self.params["file_path"])
            
            # 翻译服务和模型
            if self.params["service"]:
                if self.params["model"]:
                    command.extend(["-s", f"{self.params['service']}:{self.params['model']}"])
                else:
                    command.extend(["-s", self.params["service"]])
            
            # 语言设置
            if self.params["source_lang"]:
                command.extend(["-li", self.params["source_lang"]])
            if self.params["target_lang"]:
                command.extend(["-lo", self.params["target_lang"]])
            
            # 线程数
            if self.params["threads"] > 0:
                command.extend(["-t", str(self.params["threads"])])
            
            # 输出目录
            if self.params["output_dir"]:
                command.extend(["-o", self.params["output_dir"]])
            
            # 特定页面
            if self.params["pages"]:
                command.extend(["-p", self.params["pages"]])
            
            # 兼容模式
            if self.params["compatible_mode"]:
                command.append("-cp")
            
            # 跳过字体子集化
            if self.params["skip_subset_fonts"]:
                command.append("--skip-subset-fonts")
            
            # 设置环境变量
            env = os.environ.copy()
            if self.params["api_key"]:
                service_upper = self.params["service"].upper().replace("-", "_")
                env[f"{service_upper}_API_KEY"] = self.params["api_key"]
                
                # 特殊处理OpenAI和其他服务
                if self.params["service"] == "openai":
                    env["OPENAI_API_KEY"] = self.params["api_key"]
                elif self.params["service"] == "azure-openai":
                    env["AZURE_OPENAI_API_KEY"] = self.params["api_key"]
                elif self.params["service"] == "deepseek":
                    env["DEEPSEEK_API_KEY"] = self.params["api_key"]
                elif self.params["service"] == "silicon":
                    env["SILICON_API_KEY"] = self.params["api_key"]
                elif self.params["service"] == "tencent":
                    env["TENCENTCLOUD_SECRET_ID"] = self.params["api_key"]
                    env["TENCENTCLOUD_SECRET_KEY"] = self.params["api_url"]  # 腾讯云使用API URL字段作为SECRET_KEY
            
            if self.params["api_url"] and self.params["service"] in ["openai", "azure-openai", "xinference", "ollama"]:
                if self.params["service"] == "openai":
                    env["OPENAI_BASE_URL"] = self.params["api_url"]
                elif self.params["service"] == "azure-openai":
                    env["AZURE_OPENAI_BASE_URL"] = self.params["api_url"]
                elif self.params["service"] == "xinference":
                    env["XINFERENCE_HOST"] = self.params["api_url"]
                elif self.params["service"] == "ollama":
                    env["OLLAMA_HOST"] = self.params["api_url"]
            
            # 如果有选择模型，设置对应环境变量
            if self.params["model"] and self.params["service"] in ["openai", "azure-openai", "deepseek", "zhipu", "modelscope", "ollama", "xinference", "gemini", "silicon"]:
                service_upper = self.params["service"].upper().replace("-", "_")
                env[f"{service_upper}_MODEL"] = self.params["model"]
            
            # 显示命令
            command_str = " ".join(command)
            self.progress_signal.emit(f"执行命令: {command_str}")
            
            # 执行命令
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,
                universal_newlines=True
            )
            
            # 正则表达式匹配进度
            page_pattern = re.compile(r'Processing page (\d+) of (\d+)')
            translation_pattern = re.compile(r'Translating batch \d+/(\d+)')
            
            # 读取输出
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                
                self.progress_signal.emit(line.strip())
                
                # 解析进度
                page_match = page_pattern.search(line)
                if page_match:
                    current_page = int(page_match.group(1))
                    total_pages = int(page_match.group(2))
                    self.progress_update.emit(current_page, total_pages)
                    continue
                
                # 翻译批次进度
                trans_match = translation_pattern.search(line)
                if trans_match:
                    total_batches = int(trans_match.group(1))
                    if 'Translating batch 1/' in line:
                        self.progress_signal.emit(f"共有 {total_batches} 个翻译批次需要处理")
            
            # 获取返回码
            return_code = self.process.wait()
            
            if return_code == 0:
                self.finished_signal.emit(True, "翻译完成")
            else:
                stderr = self.process.stderr.read()
                self.finished_signal.emit(False, f"翻译失败: {stderr}")
                
        except Exception as e:
            self.finished_signal.emit(False, f"发生错误: {str(e)}")
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None


class PDF2ZHTranslator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('PDF科学论文翻译工具')
        self.setGeometry(100, 100, 800, 600)
        
        # 创建标签页
        self.tabs = QTabWidget()
        self.tab_basic = QWidget()
        self.tab_advanced = QWidget()
        self.tab_log = QWidget()
        
        self.tabs.addTab(self.tab_basic, "基本设置")
        self.tabs.addTab(self.tab_advanced, "高级设置")
        self.tabs.addTab(self.tab_log, "翻译日志")
        
        self.setup_basic_tab()
        self.setup_advanced_tab()
        self.setup_log_tab()
        
        # 设置主窗口布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("准备就绪")
        main_layout.addWidget(self.progress_bar)
        
        # 转换和取消按钮
        button_layout = QHBoxLayout()
        self.translate_button = QPushButton("开始翻译")
        self.translate_button.setFixedHeight(40)
        self.translate_button.clicked.connect(self.start_translation)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedHeight(40)
        self.cancel_button.clicked.connect(self.cancel_translation)
        self.cancel_button.setEnabled(False)
        
        button_layout.addWidget(self.translate_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        # 状态栏
        self.statusBar = QLabel("准备就绪")
        main_layout.addWidget(self.statusBar)
        
        # 设置主窗口
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # 初始化翻译线程
        self.translation_thread = None
    
    def setup_basic_tab(self):
        layout = QFormLayout()
        
        # 文件选择
        file_layout = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("选择PDF文件或输入URL")
        self.file_path.textChanged.connect(self.update_default_output_dir)
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(browse_button)
        layout.addRow("PDF文件/URL:", file_layout)
        
        # 翻译服务选择
        self.service_combo = QComboBox()
        for service_name in TRANSLATION_SERVICES.keys():
            self.service_combo.addItem(service_name)
        self.service_combo.currentIndexChanged.connect(self.update_model_options)
        layout.addRow("翻译服务:", self.service_combo)
        
        # 模型选择
        self.model_combo = QComboBox()
        self.model_combo.setEnabled(False)
        layout.addRow("模型:", self.model_combo)
        
        # API密钥
        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("输入API密钥")
        self.api_key.setEchoMode(QLineEdit.Password)
        layout.addRow("API密钥:", self.api_key)
        
        # API URL 标签更新
        self.api_url_label = QLabel("API URL:")
        # API URL
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("输入API URL (可选)")
        layout.addRow(self.api_url_label, self.api_url)
        
        # 服务变更时更新URL标签
        self.service_combo.currentIndexChanged.connect(self.update_url_label)
        
        # 语言设置
        self.source_lang = QComboBox()
        self.target_lang = QComboBox()
        
        # 添加语言选项
        for lang_name, lang_code in LANGUAGES.items():
            self.source_lang.addItem(lang_name)
            self.target_lang.addItem(lang_name)
        
        # 默认设置
        self.source_lang.setCurrentText("英语")
        self.target_lang.setCurrentText("中文(简体)")
        
        layout.addRow("源语言:", self.source_lang)
        layout.addRow("目标语言:", self.target_lang)
        
        # 输出目录
        output_layout = QHBoxLayout()
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("默认为PDF所在目录下的translated文件夹")
        output_browse = QPushButton("浏览...")
        output_browse.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.output_dir)
        output_layout.addWidget(output_browse)
        layout.addRow("输出目录:", output_layout)
        
        self.tab_basic.setLayout(layout)
        
        # 初始化模型选项
        self.update_model_options()
    
    def update_url_label(self):
        """更新API URL标签，为腾讯云翻译修改标签"""
        service_name = self.service_combo.currentText()
        service_code = TRANSLATION_SERVICES[service_name]
        
        if service_code == "tencent":
            self.api_url_label.setText("Secret Key:")
            self.api_url.setPlaceholderText("输入腾讯云 SECRET_KEY")
            self.api_url.setEchoMode(QLineEdit.Password)
        else:
            self.api_url_label.setText("API URL:")
            self.api_url.setPlaceholderText("输入API URL (可选)")
            self.api_url.setEchoMode(QLineEdit.Normal)
    
    def setup_advanced_tab(self):
        layout = QVBoxLayout()
        
        # 创建表单布局
        form_layout = QFormLayout()
        
        # 页面范围
        self.pages_input = QLineEdit()
        self.pages_input.setPlaceholderText("例如: 1-3,5 (留空翻译全文)")
        form_layout.addRow("页面范围:", self.pages_input)
        
        # 线程数
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 16)
        self.threads_spin.setValue(4)
        form_layout.addRow("线程数:", self.threads_spin)
        
        # 兼容模式
        self.compatible_mode = QCheckBox("使用兼容模式 (用于非PDF/A文档)")
        form_layout.addRow("", self.compatible_mode)
        
        # 跳过字体子集化
        self.skip_subset_fonts = QCheckBox("跳过字体子集化 (解决某些兼容性问题)")
        form_layout.addRow("", self.skip_subset_fonts)
        
        layout.addLayout(form_layout)
        
        # 保存/加载配置
        config_layout = QHBoxLayout()
        self.save_config_button = QPushButton("保存配置")
        self.save_config_button.clicked.connect(self.save_config)
        self.load_config_button = QPushButton("加载配置")
        self.load_config_button.clicked.connect(self.load_config)
        config_layout.addWidget(self.save_config_button)
        config_layout.addWidget(self.load_config_button)
        
        layout.addLayout(config_layout)
        layout.addStretch()
        
        self.tab_advanced.setLayout(layout)
    
    def setup_log_tab(self):
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        layout.addWidget(self.log_text)
        
        # 清除日志按钮
        clear_button = QPushButton("清除日志")
        clear_button.clicked.connect(self.clear_log)
        layout.addWidget(clear_button)
        
        self.tab_log.setLayout(layout)
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择PDF文件", "", "PDF文件 (*.pdf)")
        if file_path:
            self.file_path.setText(file_path)
            self.update_default_output_dir()
    
    def update_default_output_dir(self):
        """更新默认输出目录为PDF文件所在目录下的translated子文件夹"""
        file_path = self.file_path.text().strip()
        
        if file_path and not file_path.startswith(("http://", "https://")):
            # 本地文件，获取其所在目录
            pdf_dir = os.path.dirname(file_path)
            # 创建translated子目录路径
            translated_dir = os.path.join(pdf_dir, "translated")
            self.output_dir.setText(translated_dir)
        else:
            # URL或空白，清空输出目录
            self.output_dir.setText("")
    
    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir.setText(dir_path)
    
    def update_model_options(self):
        self.model_combo.clear()
        service_name = self.service_combo.currentText()
        service_code = TRANSLATION_SERVICES[service_name]
        
        if service_code in MODEL_OPTIONS and MODEL_OPTIONS[service_code]:
            self.model_combo.setEnabled(True)
            for model in MODEL_OPTIONS[service_code]:
                self.model_combo.addItem(model)
        else:
            self.model_combo.setEnabled(False)
            self.model_combo.addItem("无需选择模型")
        
        # 更新API URL标签
        self.update_url_label()
    
    def start_translation(self):
        # 检查必填参数
        file_path = self.file_path.text().strip()
        if not file_path:
            QMessageBox.warning(self, "警告", "请选择PDF文件或输入URL")
            return
        
        # 收集参数
        service_name = self.service_combo.currentText()
        service_code = TRANSLATION_SERVICES[service_name]
        
        # 确保输出目录存在
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            # 如果未指定，使用默认目录（PDF所在目录/translated）
            if not file_path.startswith(("http://", "https://")):
                pdf_dir = os.path.dirname(file_path)
                output_dir = os.path.join(pdf_dir, "translated")
            else:
                # 对于URL，使用当前工作目录下的translated子目录
                output_dir = os.path.join(os.getcwd(), "translated")
        
        # 确保输出目录存在
        try:
            os.makedirs(output_dir, exist_ok=True)
            self.output_dir.setText(output_dir)  # 更新界面显示
        except Exception as e:
            QMessageBox.warning(self, "警告", f"创建输出目录失败: {str(e)}")
            return
        
        # 检查腾讯云翻译特殊情况
        if service_code == "tencent" and not self.api_url.text().strip():
            QMessageBox.warning(self, "警告", "使用腾讯云翻译时，需要填写Secret Key")
            return
        
        params = {
            "file_path": file_path,
            "service": service_code,
            "model": self.model_combo.currentText() if self.model_combo.isEnabled() and self.model_combo.currentText() != "无需选择模型" else "",
            "source_lang": LANGUAGES[self.source_lang.currentText()],
            "target_lang": LANGUAGES[self.target_lang.currentText()],
            "api_key": self.api_key.text().strip(),
            "api_url": self.api_url.text().strip(),
            "output_dir": output_dir,
            "pages": self.pages_input.text().strip(),
            "threads": self.threads_spin.value(),
            "compatible_mode": self.compatible_mode.isChecked(),
            "skip_subset_fonts": self.skip_subset_fonts.isChecked()
        }
        
        # 检查是否需要但缺少API密钥
        if service_code not in ["google", "bing", "argos"] and not params["api_key"]:
            QMessageBox.warning(self, "警告", f"{service_name} 需要API密钥，请填写")
            return
        
        # 启动翻译线程
        self.translation_thread = TranslationThread(params)
        self.translation_thread.progress_signal.connect(self.update_log)
        self.translation_thread.progress_update.connect(self.update_progress)
        self.translation_thread.finished_signal.connect(self.translation_finished)
        
        # 更新UI状态
        self.translate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.statusBar.setText("正在翻译...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("准备中...")
        
        # 切换到日志标签页
        self.tabs.setCurrentIndex(2)
        
        # 开始翻译
        self.translation_thread.start()
        self.log_text.append("------ 翻译开始 ------")
        self.log_text.append(f"输出目录: {output_dir}")
    
    def cancel_translation(self):
        if self.translation_thread and self.translation_thread.isRunning():
            self.translation_thread.stop()
            self.log_text.append("翻译已取消")
            self.statusBar.setText("翻译已取消")
            self.translate_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress_bar.setFormat("已取消")
    
    def update_log(self, message):
        # 如果是第一条日志，添加分隔符
        if self.log_text.toPlainText().strip() == "":
            self.log_text.append("\n############# PDF2ZH Translation Start #############")
        
        # 根据不同类型的消息添加不同的颜色或样式
        if "Processing" in message:
            # 处理进度相关的消息
            self.log_text.append(f"<font color='blue'>{message}</font>")
        elif "error" in message.lower():
            # 错误消息用红色
            self.log_text.append(f"<font color='red'>{message}</font>")
        elif "Translating batch" in message:
            # 翻译批次消息用绿色
            self.log_text.append(f"<font color='green'>{message}</font>")
        else:
            # 普通消息保持默认颜色
            self.log_text.append(message)
        
        # 自动滚动到底部
        self.log_text.moveCursor(QTextCursor.End)
    
    def update_progress(self, current, total):
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.progress_bar.setFormat(f"进度: {percentage}% ({current}/{total})")
            self.statusBar.setText(f"正在处理第 {current} 页，共 {total} 页")
    
    def clear_log(self):
        self.log_text.clear()
    
    def translation_finished(self, success, message):
        self.translate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        
        if success:
            self.statusBar.setText("翻译完成")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("翻译完成 (100%)")
            self.log_text.append("------ 翻译完成 ------")
            
            # 获取输出目录和文件名
            output_dir = self.output_dir.text().strip()
            file_path = self.file_path.text().strip()
            
            # 提取文件名作为基础
            if file_path.startswith(("http://", "https://")):
                # 从URL中提取文件名
                try:
                    base_name = os.path.basename(file_path).split(".")[0]
                    if not base_name:
                        base_name = "translated"
                except:
                    base_name = "translated"
            else:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # 构建输出文件路径
            mono_path = os.path.join(output_dir, f"{base_name}-mono.pdf")
            dual_path = os.path.join(output_dir, f"{base_name}-dual.pdf")
            
            # 询问用户是否打开文件
            reply = QMessageBox.question(
                self, 
                "翻译完成", 
                f"翻译已完成，是否打开翻译结果？\n\n单语版：{mono_path}\n双语版：{dual_path}",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # 打开单语版
                if os.path.exists(mono_path):
                    self.open_file(mono_path)
                else:
                    QMessageBox.warning(self, "警告", f"找不到输出文件: {mono_path}")
        else:
            self.statusBar.setText("翻译失败")
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("翻译失败")
            self.log_text.append(f"------ 翻译失败 ------\n{message}")
            QMessageBox.critical(self, "翻译失败", message)
    
    def open_file(self, file_path):
        """使用系统默认程序打开文件"""
        import platform
        import subprocess
        
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', file_path))
            elif platform.system() == 'Windows':  # Windows
                os.startfile(file_path)
            else:  # Linux
                subprocess.call(('xdg-open', file_path))
        except Exception as e:
            QMessageBox.warning(self, "警告", f"无法打开文件: {str(e)}")
    
    def save_config(self):
        """保存当前配置到文件"""
        config = {
            "service": self.service_combo.currentText(),
            "model": self.model_combo.currentText() if self.model_combo.isEnabled() else "",
            "source_lang": self.source_lang.currentText(),
            "target_lang": self.target_lang.currentText(),
            "api_key": self.api_key.text(),
            "api_url": self.api_url.text(),
            "output_dir": self.output_dir.text(),
            "threads": self.threads_spin.value(),
            "compatible_mode": self.compatible_mode.isChecked(),
            "skip_subset_fonts": self.skip_subset_fonts.isChecked()
        }
        
        file_path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "JSON文件 (*.json)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            QMessageBox.information(self, "成功", "配置已保存")
    
    def load_config(self):
        """从文件加载配置"""
        file_path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "JSON文件 (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 应用配置
                if "service" in config:
                    self.service_combo.setCurrentText(config["service"])
                self.update_model_options()  # 更新模型选项
                
                if "model" in config and self.model_combo.isEnabled():
                    index = self.model_combo.findText(config["model"])
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                
                if "source_lang" in config:
                    self.source_lang.setCurrentText(config["source_lang"])
                if "target_lang" in config:
                    self.target_lang.setCurrentText(config["target_lang"])
                if "api_key" in config:
                    self.api_key.setText(config["api_key"])
                if "api_url" in config:
                    self.api_url.setText(config["api_url"])
                if "output_dir" in config:
                    self.output_dir.setText(config["output_dir"])
                if "threads" in config:
                    self.threads_spin.setValue(config["threads"])
                if "compatible_mode" in config:
                    self.compatible_mode.setChecked(config["compatible_mode"])
                if "skip_subset_fonts" in config:
                    self.skip_subset_fonts.setChecked(config["skip_subset_fonts"])
                
                QMessageBox.information(self, "成功", "配置已加载")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDF2ZHTranslator()
    window.show()
    sys.exit(app.exec_())
