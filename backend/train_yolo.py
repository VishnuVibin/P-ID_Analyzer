import os
import shutil
from ultralytics import YOLO

def train():
    # Load a pretrained model
    model = YOLO("yolov8n.pt")

    # Define training settings
    data_path = "d:/Pid_symbol/archive_4_resized/data.yaml"
    epochs = 15
    batch_size = 8
    img_size = 640
    device = 0 # GPU
    
    print(f"Training YOLOv8n for {epochs} epochs with batch={batch_size} and imgsz={img_size} on GPU...")
    
    # Train the model
    results = model.train(
        data=data_path,
        epochs=epochs,
        imgsz=img_size,
        batch=batch_size,
        device=device,
        workers=2,
        cache=False
    )
    
    print("Training complete! Copying weights...")
    
    # Locate best weights
    best_weights_src = os.path.join("runs", "detect", "train", "weights", "best.pt")
    # If there are multiple training run directories, check for the latest one
    run_idx = 2
    while not os.path.exists(best_weights_src):
        candidate = os.path.join("runs", "detect", f"train{run_idx}", "weights", "best.pt")
        if os.path.exists(candidate):
            best_weights_src = candidate
            break
        run_idx += 1
        if run_idx > 50:
            break
            
    if os.path.exists(best_weights_src):
        dst_dir = os.path.join(os.path.dirname(__file__), "weights")
        os.makedirs(dst_dir, exist_ok=True)
        best_weights_dst = os.path.join(dst_dir, "yolo_symbol_best.pt")
        shutil.copy(best_weights_src, best_weights_dst)
        print(f"Successfully saved trained weights to {best_weights_dst}")
    else:
        print("Error: Could not locate trained weights file 'best.pt'")

if __name__ == "__main__":
    train()
