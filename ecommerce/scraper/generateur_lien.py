import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout,
    QFileDialog, QLineEdit, QTextEdit, QMessageBox, QHBoxLayout
)
from PySide6.QtGui import QClipboard
import sys

class WooImageURLGenerator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("G\u00e9n\u00e9rateur de Liens WooCommerce")

        self.layout = QVBoxLayout()

        # Domaine
        self.label_base_url = QLabel("Domaine WooCommerce :")
        self.input_base_url = QLineEdit("https://www.planetebob.fr")
        self.layout.addWidget(self.label_base_url)
        self.layout.addWidget(self.input_base_url)

        # Ann\u00e9e/mois
        self.label_date = QLabel("Date (format YYYY/MM) :")
        self.input_date = QLineEdit("2025/07")
        self.layout.addWidget(self.label_date)
        self.layout.addWidget(self.input_date)

        # Choix du dossier
        self.btn_select_folder = QPushButton("Choisir le dossier d'images")
        self.btn_select_folder.clicked.connect(self.choose_folder)
        self.layout.addWidget(self.btn_select_folder)

        # Zone affichage
        self.output_links = QTextEdit()
        self.output_links.setPlaceholderText("Les URLs g\u00e9n\u00e9r\u00e9es s'afficheront ici.")
        self.layout.addWidget(self.output_links)

        # Boutons actions
        action_layout = QHBoxLayout()

        self.btn_generate = QPushButton("G\u00e9n\u00e9rer")
        self.btn_generate.clicked.connect(self.generate_links)
        action_layout.addWidget(self.btn_generate)

        self.btn_copy = QPushButton("Copier les liens")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        action_layout.addWidget(self.btn_copy)

        self.btn_export = QPushButton("Exporter en .txt")
        self.btn_export.clicked.connect(self.export_to_txt)
        action_layout.addWidget(self.btn_export)

        self.layout.addLayout(action_layout)

        self.setLayout(self.layout)

        self.folder_path = ""

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "S\u00e9lectionner un dossier")
        if folder:
            self.folder_path = folder
            self.btn_select_folder.setText(f"Dossier : {os.path.basename(folder)}")

    def generate_links(self):
        if not self.folder_path:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir un dossier.")
            return

        base_url = self.input_base_url.text().strip().rstrip("/")
        date_path = self.input_date.text().strip()

        links = []
        for root, _, files in os.walk(self.folder_path):
            for file in files:
                if file.lower().endswith((
                    '.webp', '.jpg', '.jpeg', '.png'
                )):
                    file_url = (
                        f"{base_url}/wp-content/uploads/{date_path}/{file}"
                    )
                    links.append(file_url)

        if links:
            self.output_links.setText("\n".join(links))
        else:
            self.output_links.setText("Aucune image valide trouv\u00e9e dans le dossier.")

    def copy_to_clipboard(self):
        clipboard: QClipboard = QApplication.clipboard()
        clipboard.setText(self.output_links.toPlainText())
        QMessageBox.information(self, "Copi\u00e9", "Les liens ont \u00e9t\u00e9 copi\u00e9s dans le presse-papiers.")

    def export_to_txt(self):
        if not self.output_links.toPlainText():
            QMessageBox.warning(self, "Erreur", "Aucun lien \u00e0 exporter.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer sous", "liens_images.txt", "Fichier texte (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.output_links.toPlainText())
            QMessageBox.information(self, "Export\u00e9", "Les liens ont \u00e9t\u00e9 enregistr\u00e9s avec succ\u00e8s.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WooImageURLGenerator()
    window.resize(700, 500)
    window.show()
    sys.exit(app.exec())
