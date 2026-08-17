import os
import cv2
from detector import PIDDetector

def test():
    print("Testing detector with YOLOv8 symbol model...")
    detector = PIDDetector()
    
    # Verify symbol model is found
    model = detector.get_symbol_model()
    if model is None:
        print("Error: Could not load the trained symbol model!")
        return
        
    print(f"Loaded symbol model: {model.ckpt_path} with {len(model.names)} classes.")
    
    # Load test image
    test_img_path = "d:/Pid_symbol/archive_4_resized/images/test/images__train__113.jpg"
    if not os.path.exists(test_img_path):
        print(f"Error: Test image not found at {test_img_path}")
        return
        
    img = cv2.imread(test_img_path)
    print(f"Loaded test image from {test_img_path} with shape {img.shape}")
    
    # Mock text blocks (OCR results)
    text_blocks = [
        {'text': 'PV-101', 'bbox': [100, 100, 150, 120]},
        {'text': 'FCV-102', 'bbox': [300, 300, 380, 320]},
    ]
    
    symbols, grouped_text_blocks = detector.detect_symbols(img, text_blocks)
    
    print(f"\nDetection complete! Found {len(symbols)} symbols.")
    for idx, s in enumerate(symbols):
        print(f"Symbol #{idx}:")
        print(f"  ID: {s['id']}")
        print(f"  Tag: {s['tag']}")
        print(f"  Type: {s['type']}")
        print(f"  Class ID: {s['class_id']}")
        print(f"  Bbox: {s['bbox']}")
        print(f"  Center: {s['center']}")

if __name__ == "__main__":
    test()
