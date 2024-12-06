import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QSlider, QHBoxLayout, QVBoxLayout, 
                             QPushButton, QFileDialog, QMessageBox, QGroupBox, QColorDialog, QFrame, QScrollArea)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QColor, QPalette

MAX_MAPPINGS = 10

class ColorMappingWidget(QGroupBox):
    """
    A widget representing a single color mapping:
    - Sliders for lower and upper B/G/R thresholds
    - A color picker for the replacement color
    - A remove button
    
    Emits changes via callbacks passed in constructor.
    """
    def __init__(self, index, remove_callback, update_callback):
        super().__init__(f"Color Mapping #{index+1}")
        
        self.index = index
        self.remove_callback = remove_callback
        self.update_callback = update_callback

        self.lower_color = np.array([200, 200, 200], dtype=np.uint8)
        self.upper_color = np.array([255, 255, 255], dtype=np.uint8)
        self.new_line_color = [0, 255, 0]

        # Create sliders
        self.l_b_slider = self.create_slider(self.lower_color[0], self.slider_changed)
        self.l_g_slider = self.create_slider(self.lower_color[1], self.slider_changed)
        self.l_r_slider = self.create_slider(self.lower_color[2], self.slider_changed)

        self.u_b_slider = self.create_slider(self.upper_color[0], self.slider_changed)
        self.u_g_slider = self.create_slider(self.upper_color[1], self.slider_changed)
        self.u_r_slider = self.create_slider(self.upper_color[2], self.slider_changed)

        # Color picker button
        self.color_btn = QPushButton("Pick Replacement Color")
        self.color_btn.clicked.connect(self.pick_color)

        # Remove button
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(lambda: self.remove_callback(self.index))

        # Layout
        # Sliders layout
        sliders_layout = QVBoxLayout()

        sliders_layout.addWidget(QLabel("Lower B:"))
        sliders_layout.addWidget(self.l_b_slider)
        sliders_layout.addWidget(QLabel("Lower G:"))
        sliders_layout.addWidget(self.l_g_slider)
        sliders_layout.addWidget(QLabel("Lower R:"))
        sliders_layout.addWidget(self.l_r_slider)

        sliders_layout.addWidget(QLabel("Upper B:"))
        sliders_layout.addWidget(self.u_b_slider)
        sliders_layout.addWidget(QLabel("Upper G:"))
        sliders_layout.addWidget(self.u_g_slider)
        sliders_layout.addWidget(QLabel("Upper R:"))
        sliders_layout.addWidget(self.u_r_slider)

        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.color_btn)
        btn_layout.addWidget(self.remove_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(sliders_layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        self.update_style()

    def create_slider(self, init_val, slot):
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 255)
        s.setValue(init_val)
        s.valueChanged.connect(slot)
        return s

    def slider_changed(self):
        self.lower_color = np.array([
            self.l_b_slider.value(),
            self.l_g_slider.value(),
            self.l_r_slider.value()
        ], dtype=np.uint8)

        self.upper_color = np.array([
            self.u_b_slider.value(),
            self.u_g_slider.value(),
            self.u_r_slider.value()
        ], dtype=np.uint8)

        self.update_callback()

    def pick_color(self):
        color = QColorDialog.getColor(QColor(*self.new_line_color), self, "Pick Replacement Color")
        if color.isValid():
            self.new_line_color = [color.blue(), color.green(), color.red()]
            self.update_callback()

    def update_style(self):
        # A slightly more modern look
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                font: 13px 'Arial';
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
                background-color: #f0f0f0;
                border-radius: 3px;
            }
            QLabel {
                font: 12px 'Arial';
            }
            QPushButton {
                background-color: #e1e1e1;
                border: 1px solid #aaa;
                border-radius: 3px;
                padding: 3px 6px;
            }
            QPushButton:hover {
                background-color: #d7d7d7;
            }
        """)


class VideoPlayer(QWidget):
    def __init__(self, video_path=None):
        super().__init__()
        self.setWindowTitle("Advanced Video Color Adjuster")

        # Video attributes
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.playing = False

        # Store multiple mappings (each a ColorMappingWidget)
        self.mappings = []

        # Create UI
        self.init_ui()

        # If a video path is provided at start
        if video_path:
            self.load_new_video(video_path)

    def init_ui(self):
        # Instructions
        instructions = QLabel(
            "Instructions:\n"
            "1. Click 'Load Video' to select a video file.\n"
            "2. Use the 'Add Color Mapping' button to add up to 10 color transformations.\n"
            "3. For each mapping, adjust the B/G/R lower and upper sliders to target a specific original color range in the video.\n"
            "4. Click 'Pick Replacement Color' to choose the new color for that range.\n"
            "5. Press 'Play' to preview changes. Adjust sliders as needed until the desired look is achieved.\n"
            "6. When satisfied, click 'Apply & Save' to render and save a new video with all changes applied.\n"
            "\n"
            "Tips:\n"
            "- Add multiple mappings to change multiple colors simultaneously.\n"
            "- Removal of a mapping resets that transformation.\n"
            "- The displayed frame updates live (when paused) or as the video plays.\n"
        )
        instructions.setStyleSheet("font: 12px 'Arial';")

        self.video_label = QLabel("No Video Loaded")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: white; border: 1px solid #ddd;")

        # Buttons
        self.load_btn = QPushButton("Load Video")
        self.load_btn.clicked.connect(self.load_video)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_play)
        self.apply_btn = QPushButton("Apply & Save")
        self.apply_btn.clicked.connect(self.apply_and_save)

        self.add_mapping_btn = QPushButton("Add Color Mapping")
        self.add_mapping_btn.clicked.connect(self.add_mapping)

        # Layout for color mappings
        self.mappings_layout = QVBoxLayout()
        self.mappings_layout.addWidget(self.add_mapping_btn)
        self.mappings_layout.addStretch(1)

        # Put mappings in a scroll area in case we have many
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.mappings_layout)
        scroll = QScrollArea()
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: #fafafa; border:1px solid #ccc;")

        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.apply_btn)

        main_layout = QVBoxLayout()
        # Instructions frame
        instructions_frame = QFrame()
        instructions_frame.setFrameShape(QFrame.StyledPanel)
        instructions_frame.setLayout(QVBoxLayout())
        instructions_frame.layout().addWidget(instructions)

        main_layout.addWidget(instructions_frame)
        main_layout.addWidget(self.video_label)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)
        self.resize(1000, 700)

        self.update_style()

    def update_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #fdfdfd;
                font: 14px 'Arial';
            }
            QPushButton {
                background-color: #eee;
                border: 1px solid #aaa;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #ddd;
            }
            QLabel {
                font: 13px 'Arial';
            }
        """)

    def add_mapping(self):
        if len(self.mappings) >= MAX_MAPPINGS:
            QMessageBox.warning(self, "Limit Reached", f"You can only add up to {MAX_MAPPINGS} color mappings.")
            return

        index = len(self.mappings)
        mapping_widget = ColorMappingWidget(index, self.remove_mapping, self.mapping_changed)
        self.mappings.insert(index, mapping_widget)
        self.mappings_layout.insertWidget(index, mapping_widget)

    def remove_mapping(self, index):
        # Remove the mapping widget and entry
        widget = self.mappings[index]
        self.mappings_layout.removeWidget(widget)
        widget.deleteLater()
        self.mappings.pop(index)

        # Re-label subsequent mappings
        for i, mw in enumerate(self.mappings):
            mw.setTitle(f"Color Mapping #{i+1}")
            mw.index = i

        self.mapping_changed()

    def mapping_changed(self):
        # If not playing, preview the current frame with changes
        if not self.playing:
            self.update_frame()

    def load_video(self):
        file_dialog = QFileDialog(self, "Select Video File")
        file_dialog.setNameFilter("Video Files (*.mp4 *.avi *.mov)")
        if file_dialog.exec_():
            file_path = file_dialog.selectedFiles()[0]
            self.load_new_video(file_path)

    def load_new_video(self, file_path):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

        self.cap = cv2.VideoCapture(file_path)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", "Could not open video.")
            return
        self.play_btn.setText("Play")
        self.playing = False
        self.timer.stop()
        self.update_frame()  # Show first frame

    def toggle_play(self):
        if self.cap is None or not self.cap.isOpened():
            return
        self.playing = not self.playing
        if self.playing:
            self.play_btn.setText("Pause")
            self.timer.start(int(1000/30))  # approx 30 fps
        else:
            self.play_btn.setText("Play")
            self.timer.stop()

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        total_frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)

        if current_pos >= total_frames:
            # End of video
            if self.playing:
                self.timer.stop()
            self.playing = False
            self.play_btn.setText("Play")
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # rewind
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        # Store original frame to ensure multiple mappings don't override each other's source pixels
        original_frame = frame.copy()

        # Apply multiple mappings
        # For each mapping, we create a mask and replace pixels accordingly
        # We'll do this step-by-step so that each mapping only affects pixels that match the original source conditions.
        # If you want them to stack, this approach ensures each mapping checks original_frame not the already modified frame.
        for mw in self.mappings:
            # Create mask from original_frame based on mw's lower_color, upper_color
            mask = cv2.inRange(original_frame, mw.lower_color, mw.upper_color)
            # Apply to frame
            frame[mask != 0] = mw.new_line_color

        # Convert to Qt image
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_img))

    def apply_and_save(self):
        if self.cap is None or not self.cap.isOpened():
            QMessageBox.warning(self, "No Video", "No video loaded to apply changes.")
            return

        # Ask user for save path
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Video", "", "MP4 Files (*.mp4)")
        if not save_path:
            return

        # Stop playback
        self.playing = False
        self.play_btn.setText("Play")
        self.timer.stop()

        # Rewind video
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(save_path, fourcc, fps, (width, height))

        # Process entire video with current mappings
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            original_frame = frame.copy()
            for mw in self.mappings:
                mask = cv2.inRange(original_frame, mw.lower_color, mw.upper_color)
                frame[mask != 0] = mw.new_line_color
            out.write(frame)

        out.release()
        # Rewind original video
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.update_frame()
        QMessageBox.information(self, "Done", "Video saved successfully!")

    def closeEvent(self, event):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        event.accept()

def main():
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
