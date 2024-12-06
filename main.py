import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QSlider, QHBoxLayout, QVBoxLayout, QPushButton, QFileDialog, QMessageBox)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

class VideoPlayer(QWidget):
    def __init__(self, video_path=None):
        super().__init__()
        self.setWindowTitle("Video Color Adjuster")

        # Video attributes
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.playing = False

        # Default color ranges (for replacing line colors)
        # Example: we start with a range that might isolate white lines
        self.lower_color = np.array([200, 200, 200], dtype=np.uint8)
        self.upper_color = np.array([255, 255, 255], dtype=np.uint8)
        self.new_line_color = [0, 255, 0]  # green

        # UI Elements
        self.video_label = QLabel("No Video Loaded")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")

        # Sliders for lower and upper BGR
        self.l_b_slider = self.create_slider(0, 255, self.lower_color[0], self.slider_changed)
        self.l_g_slider = self.create_slider(0, 255, self.lower_color[1], self.slider_changed)
        self.l_r_slider = self.create_slider(0, 255, self.lower_color[2], self.slider_changed)

        self.u_b_slider = self.create_slider(0, 255, self.upper_color[0], self.slider_changed)
        self.u_g_slider = self.create_slider(0, 255, self.upper_color[1], self.slider_changed)
        self.u_r_slider = self.create_slider(0, 255, self.upper_color[2], self.slider_changed)

        # Buttons
        self.load_btn = QPushButton("Load Video")
        self.load_btn.clicked.connect(self.load_video)

        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_play)

        self.apply_btn = QPushButton("Apply & Save")
        self.apply_btn.clicked.connect(self.apply_and_save)

        # Layout
        sliders_layout = QVBoxLayout()
        sliders_layout.addWidget(QLabel("Lower B"))
        sliders_layout.addWidget(self.l_b_slider)
        sliders_layout.addWidget(QLabel("Lower G"))
        sliders_layout.addWidget(self.l_g_slider)
        sliders_layout.addWidget(QLabel("Lower R"))
        sliders_layout.addWidget(self.l_r_slider)
        sliders_layout.addWidget(QLabel("Upper B"))
        sliders_layout.addWidget(self.u_b_slider)
        sliders_layout.addWidget(QLabel("Upper G"))
        sliders_layout.addWidget(self.u_g_slider)
        sliders_layout.addWidget(QLabel("Upper R"))
        sliders_layout.addWidget(self.u_r_slider)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.apply_btn)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.video_label)
        main_layout.addLayout(sliders_layout)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)
        self.resize(800, 600)

        # If a video path is provided at start
        if video_path:
            self.load_new_video(video_path)

    def create_slider(self, min_val, max_val, init_val, slot):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_val, max_val)
        s.setValue(init_val)
        s.valueChanged.connect(slot)
        return s

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
            self.timer.start(30)  # about ~33fps
        else:
            self.play_btn.setText("Play")
            self.timer.stop()

    def slider_changed(self):
        # Update the color range based on slider values
        self.lower_color = np.array([self.l_b_slider.value(), self.l_g_slider.value(), self.l_r_slider.value()], dtype=np.uint8)
        self.upper_color = np.array([self.u_b_slider.value(), self.u_g_slider.value(), self.u_r_slider.value()], dtype=np.uint8)
        # If not playing, update the frame to preview the changes
        if not self.playing:
            self.update_frame()

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

        # Apply color mask
        mask = cv2.inRange(frame, self.lower_color, self.upper_color)
        frame[mask != 0] = self.new_line_color

        # Convert to Qt image
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_img))

    def apply_and_save(self):
        # Ask user for save path
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Video", "", "MP4 Files (*.mp4)")
        if not save_path:
            return

        # Re-process entire video with current settings and save
        if self.cap is None or not self.cap.isOpened():
            QMessageBox.warning(self, "No Video", "No video loaded to apply changes.")
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

        # Process frames
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            mask = cv2.inRange(frame, self.lower_color, self.upper_color)
            frame[mask != 0] = self.new_line_color
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
