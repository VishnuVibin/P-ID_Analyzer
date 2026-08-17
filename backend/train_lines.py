import os
import shutil
import numpy as np
from PIL import Image
from datasets import load_dataset
from ultralytics import YOLO

os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

def segment_to_polygon(x1, y1, x2, y2, thickness=3.0):
    dx = x2 - x1
    dy = y2 - y1
    length = np.hypot(dx, dy)
    if length == 0:
        return [x1 - thickness, y1 - thickness, x1 + thickness, y1 - thickness, x1 + thickness, y1 + thickness, x1 - thickness, y1 + thickness]
    
    nx = -dy / length
    ny = dx / length
    
    offset_x = nx * (thickness / 2.0)
    offset_y = ny * (thickness / 2.0)
    
    p1 = (x1 + offset_x, y1 + offset_y)
    p2 = (x1 - offset_x, y1 - offset_y)
    p3 = (x2 - offset_x, y2 - offset_y)
    p4 = (x2 + offset_x, y2 + offset_y)
    
    return [p1[0], p1[1], p2[0], p2[1], p3[0], p3[1], p4[0], p4[1]]

def prepare_yolo_segmentation_dataset():
    print("Loading Hugging Face lines-dataset...")
    try:
        ds = load_dataset("prasatee/lines-dataset")
    except Exception as e:
        print("Error loading dataset:", e)
        return None
        
    dataset_dir = "d:/Pid_symbol/lines_yolo_dataset"
    os.makedirs(os.path.join(dataset_dir, "images", "train"), exist_ok=True)
    os.makedirs(os.path.join(dataset_dir, "images", "val"), exist_ok=True)
    os.makedirs(os.path.join(dataset_dir, "labels", "train"), exist_ok=True)
    os.makedirs(os.path.join(dataset_dir, "labels", "val"), exist_ok=True)
    
    # We will map line types to class IDs dynamically
    class_map = {}
    class_counter = 0
    
    for split in ["train", "test"]:
        yolo_split = "train" if split == "train" else "val"
        print(f"Processing split: {split} -> {yolo_split}")
        
        split_data = ds[split]
        # Limit to first 100 images to keep training dataset size manageable for local execution
        num_images = min(100, len(split_data))
        
        for idx in range(num_images):
            item = split_data[idx]
            img = item["image"]
            width, height = img.size
            
            img_filename = f"img_{idx}.jpg"
            img_path = os.path.join(dataset_dir, "images", yolo_split, img_filename)
            img.save(img_path)
            
            # Label conversion
            label_filename = f"img_{idx}.txt"
            label_path = os.path.join(dataset_dir, "labels", yolo_split, label_filename)
            
            lines_dict = item.get("lines", {})
            segments = lines_dict.get("segments", [])
            line_types = lines_dict.get("line_types", [])
            
            with open(label_path, "w") as f:
                for seg, l_type in zip(segments, line_types):
                    if l_type not in class_map:
                        class_map[l_type] = class_counter
                        class_counter += 1
                        
                    class_id = class_map[l_type]
                    
                    if len(seg) == 4:
                        y1, x1, y2, x2 = seg # Assuming y1, x1, y2, x2 format typically used
                        polygon = segment_to_polygon(x1, y1, x2, y2, thickness=3.0)
                        
                        # Normalize coordinates
                        norm_poly = []
                        for i in range(0, len(polygon), 2):
                            px = polygon[i] / width
                            py = polygon[i+1] / height
                            norm_poly.append(f"{px:.6f} {py:.6f}")
                        
                        poly_str = " ".join(norm_poly)
                        f.write(f"{class_id} {poly_str}\n")
                        
    # Write data.yaml
    data_yaml_path = os.path.join(dataset_dir, "data.yaml")
    class_names = [k for k, v in sorted(class_map.items(), key=lambda x: x[1])]
    
    with open(data_yaml_path, "w") as f:
        f.write(f"path: {dataset_dir}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n\n")
        f.write("names:\n")
        for cid, cname in enumerate(class_names):
            f.write(f"  {cid}: {cname}\n")
            
    print("Dataset preparation complete!")
    print(f"Data YAML written to {data_yaml_path}")
    print(f"Classes found: {class_map}")
    return data_yaml_path

def train_yolo_seg(data_yaml_path):
    if not data_yaml_path:
        print("Data YAML not found. Skipping training.")
        return
        
    print("Initializing pretrained YOLOv8n-seg model...")
    model = YOLO("yolov8n-seg.pt")
    
    epochs = 3
    batch_size = 4
    img_size = 640
    
    print(f"Training YOLOv8n-seg for {epochs} epochs...")
    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        imgsz=img_size,
        batch=batch_size,
        device="cpu", # Default to CPU to ensure compatibility across client setups
        workers=0,
        cache=False
    )
    
    # Locate best weights
    best_weights_src = os.path.join("runs", "segment", "train", "weights", "best.pt")
    run_idx = 2
    while not os.path.exists(best_weights_src):
        candidate = os.path.join("runs", "segment", f"train{run_idx}", "weights", "best.pt")
        if os.path.exists(candidate):
            best_weights_src = candidate
            break
        run_idx += 1
        if run_idx > 50:
            break
            
    if os.path.exists(best_weights_src):
        dst_dir = os.path.join(os.path.dirname(__file__), "weights")
        os.makedirs(dst_dir, exist_ok=True)
        best_weights_dst = os.path.join(dst_dir, "yolo_lines_best.pt")
        shutil.copy(best_weights_src, best_weights_dst)
        print(f"Successfully saved line segmentation model weights to {best_weights_dst}")
    else:
        print("Could not locate trained weights file 'best.pt'")

if __name__ == "__main__":
    yaml_path = prepare_yolo_segmentation_dataset()
    if yaml_path:
        train_yolo_seg(yaml_path)
