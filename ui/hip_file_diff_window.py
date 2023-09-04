import sys
import os
import random
import zipfile
# from PySide2.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, 
#                                QHBoxLayout, QLineEdit, QPushButton, 
#                                QTreeView, QSplitter, QMessageBox)
# from PySide2.QtCore import Qt
# from PySide2.QtGui import QStandardItemModel, QStandardItem

from hutil.Qt.QtGui import *
from hutil.Qt.QtCore import *
from hutil.Qt.QtWidgets import *
import hou


from api.hip_file_comparator import HipFileComparator, SUPPORTED_FILE_FORMATS


current_dir = os.path.dirname(os.path.abspath(__file__))
ICONS_ZIP_PATH = os.path.join(current_dir, 'icons')
ICONS_MAPPING_PATH = os.path.join(ICONS_ZIP_PATH, 'IconMapping')
ICONS_ZIP_PATH = os.path.join(ICONS_ZIP_PATH, 'icons.zip')

ICON_MAPPINGS = {}
with open(ICONS_MAPPING_PATH, 'r') as file:
    for line in file:
        if line.startswith("#") or ":=" not in line:
            continue

        key, value = line.split(":=")
        key = key.strip()
        value = value.strip().rstrip(";")
        ICON_MAPPINGS[key] = value.replace("_", "/", 1)


class CustomStandardItemModel(QStandardItemModel):
    def __init__(self, *args, **kwargs):
        super(CustomStandardItemModel, self).__init__(*args, **kwargs)
        self.item_dictionary = {}
        self.path_role = Qt.UserRole + 1
        self.data_role = Qt.UserRole + 1

    def add_item_with_path(
            self, 
            item_text, 
            path, 
            data, 
            parent=None,
            icons_zip=None
        ):
        """Adds an item to the model with a unique identifier."""
        item = QStandardItem(item_text)
        item.setData(path, self.path_role)
        item.setData(data, self.data_role)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        # Store the item reference in the dictionary
        self.item_dictionary[path] = item

        if icons_zip:
            try:
                icon_path_inside_zip = ICON_MAPPINGS[data["icon"]]

                with icons_zip.open(icon_path_inside_zip) as file:
                    data = file.read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                    qicon = QIcon(pixmap)
                    item.setIcon(qicon)
            except Exception as e:
                print(e)
                pass

        if parent:
            parent.appendRow(item)
        else:
            self.appendRow(item)

    def get_item_by_path(self, path):
        """Retrieve an item based on its unique identifier."""
        return self.item_dictionary.get(path)


class HipFileDiffWindow(QMainWindow):
    def __init__(self):
        super(HipFileDiffWindow, self).__init__()
        
        # Set window properties
        self.setWindowTitle('.hip files diff tool')
        self.setGeometry(300, 300, 1000, 800)

        # Main widget to set as central widget
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)

        # Main vertical layout
        self.main_layout = QVBoxLayout(self.main_widget)

        main_stylesheet = """
            QMainWindow{
                background-color: #333;
            }
            QLineEdit {
                font: 12pt "Arial";
                color: #FFFFFF;
                background-color: #333333;
                border: 1px solid black;
                border-radius: 5px;
                padding: 4px;
            }
            QPushButton {
                font: 12pt "Arial";
                color: #FFFFFF;
                background-color: #555555;
                border: 1px solid black;
                border-radius: 5px;
                padding: 4px;

            }
            QTreeView {
                font: 12pt "Arial";
                color: #FFFFFF;
                background-color: #333333;
                border: 1px solid black;
                border-radius: 5px;
                padding: 4px;
            }
        """

        self.setStyleSheet(main_stylesheet)

        # Horizontal layout at the top
        self.source_file_line_edit = QLineEdit(self)
        self.source_file_line_edit.setText("C:/Users/golub/Documents/hip_file_diff_tool/test_scenes/billowy_smoke_source.hipnc")
        self.source_file_line_edit.setMinimumWidth(100)
        self.source_file_line_edit.setPlaceholderText("source_file_line_edit")

        self.target_file_line_edit = QLineEdit(self)        
        self.target_file_line_edit.setText("C:/Users/golub/Documents/hip_file_diff_tool/test_scenes/billowy_smoke_source_edited.hipnc")
        self.target_file_line_edit.setMinimumWidth(100)
        self.target_file_line_edit.setPlaceholderText("target_file_line_edit")
        
        self.load_button = QPushButton("Load scenes", self)
        self.load_button.clicked.connect(self.handle_load_button_click)
        self.load_button.setMinimumWidth(100)

        self.top_hlayout = QHBoxLayout()
        self.top_hlayout.addWidget(self.source_file_line_edit)
        self.top_hlayout.addWidget(self.target_file_line_edit)
        self.top_hlayout.addWidget(self.load_button)
        self.main_layout.addLayout(self.top_hlayout)

        # splitter = QSplitter(Qt.Horizontal, self)
        # self.main_layout.addWidget(splitter)

        self.treeviews_layout = QHBoxLayout()
        self.main_layout.addLayout(self.treeviews_layout)

        # Splitter for three QTreeViews

        self.source_treeview = QTreeView(self)
        self.target_treeview = QTreeView(self)

        self.treeviews_layout.addWidget(self.source_treeview)
        self.treeviews_layout.addWidget(self.target_treeview)

        self.populate_tree_with_data("source", self.source_treeview, {})

        self.hip_comparator = None
        self.load_button.click()

    def populate_tree_with_data(
            self, 
            name,
            treeview, 
            data
    ):
        model = CustomStandardItemModel()
        model.setHorizontalHeaderLabels([name])

        with zipfile.ZipFile(ICONS_ZIP_PATH, 'r') as zip_ref:
            for path in data:
                node_data = data[path]

                node_name = node_data["name"]
                parent_path = node_data["parent_path"]
                parent_item = model.get_item_by_path(parent_path)

                # print(node_name, path, parent_path, node_data["icon"])
                model.add_item_with_path(
                    node_name, 
                    path, 
                    node_data, 
                    parent=parent_item,
                    icons_zip=zip_ref
                )
        
        treeview.setModel(model)

    def handle_load_button_click(self):

        source_scene_path = self.source_file_line_edit.text().strip('"')
        self.check_file_path(source_scene_path)
        
        target_scene_path = self.target_file_line_edit.text().strip('"')
        self.check_file_path(target_scene_path)

        self.hip_comparator = HipFileComparator(
            source_scene_path, 
            target_scene_path
        )        
        self.hip_comparator.compare()

        if self.hip_comparator.is_compared != True:
            error_during_comparasing_text = "There was an error during file comparasing"
            QMessageBox.critical(
                self, 
                "Error", 
                error_during_comparasing_text
            )
            raise RuntimeError(error_during_comparasing_text)
            
        self.populate_tree_with_data(
            "source",
            self.source_treeview, 
            self.hip_comparator.source_data
        )

        self.populate_tree_with_data(
            "target",
            self.source_treeview, 
            self.hip_comparator.target_data
        )


    def check_file_path(self, path):
        if not os.path.exists(path):
            incorrect_path_text = "Incorrect source path specified, such file don't exists."
            QMessageBox.critical(self, "Error", incorrect_path_text)
            raise RuntimeError(incorrect_path_text)
        
        _, extension = os.path.splitext(path)
        print("_, extension", _, extension)
        if extension[1:] not in SUPPORTED_FILE_FORMATS:
            only_hip_supported_text = "Incorrect source file specified, only .hip files supported."
            QMessageBox.critical(self, "Error", only_hip_supported_text)
            raise RuntimeError(only_hip_supported_text)


