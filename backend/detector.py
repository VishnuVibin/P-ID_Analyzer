import os
import re
import cv2
import numpy as np
import pymupdf  # PyMuPDF
import pandas as pd

class PIDDetector:
    def __init__(self):
        self.yolo_model_path = os.path.join(
            os.path.dirname(__file__), 
            "pipeline_tracer.v1i.yolov8 (1)", 
            "runs", "segment", "train", "weights", "best.pt"
        )
        self.yolo_model = None
        # YOLO is loaded lazily only if the model file exists and connection tracing needs it.
        
        self.symbol_model = None
        self.ocr_reader = None

    def get_symbol_model(self):
        if self.symbol_model is None:
            # Find best weights paths
            paths_to_check = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "detect", "train-3", "weights", "best.pt"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "detect", "train-2", "weights", "best.pt"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs", "detect", "train", "weights", "best.pt"),
                os.path.join(os.path.dirname(__file__), "weights", "yolo_symbol_best.pt"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "yolov8n.pt")
            ]
            for p in paths_to_check:
                if os.path.exists(p):
                    try:
                        from ultralytics import YOLO
                        m = YOLO(p)
                        if len(m.names) > 80: # Symbol detector has 203 classes
                            self.symbol_model = m
                            print(f"Successfully loaded YOLO symbol model from {p} with {len(m.names)} classes.")
                            break
                    except Exception as e:
                        print(f"Error loading symbol model from {p}: {e}")
        return self.symbol_model

    def get_ocr_reader(self):
        if self.ocr_reader is None:
            # Import and initialize EasyOCR only when OCR is actually required.
            import easyocr
            self.ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        return self.ocr_reader

        doc = pymupdf.open(pdf_path)
        try:
            if page_num >= len(doc):
                page_num = 0
            page = doc.load_page(page_num)

            # Render at a controlled resolution to avoid excessive RAM usage on Render.
            # 200 DPI is substantially smaller than the previous 4x zoom.
            target_dpi = 200
            zoom = target_dpi / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img_bytes = pix.tobytes("jpg", jpg_quality=85)
            file_bytes = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

            # Hard cap image dimensions so very large P&IDs cannot exhaust memory.
            max_dim = 3000
            h, w = img.shape[:2]
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(
                    img,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_AREA
                )
                # Keep text coordinates consistent with the resized image.
                coord_scale = scale
            else:
                coord_scale = 1.0

            text_blocks = []
            words = page.get_text("words")
            if words:
                temp_lines = {}
                for w in words:
                    x0, y0, x1, y1, word, block_idx, line_idx, _ = w
                    rx0 = x0 * zoom * coord_scale
                    ry0 = y0 * zoom * coord_scale
                    rx1 = x1 * zoom * coord_scale
                    ry1 = y1 * zoom * coord_scale
                    key = (block_idx, line_idx)
                    if key not in temp_lines:
                        temp_lines[key] = []
                    temp_lines[key].append({
                        'text': word,
                        'bbox': [rx0, ry0, rx1, ry1]
                    })

                for key, line_words in temp_lines.items():
                    line_words.sort(key=lambda item: item['bbox'][0])
                    merged_text = ""
                    min_x0 = float('inf')
                    min_y0 = float('inf')
                    max_x1 = float('-inf')
                    max_y1 = float('-inf')
                    for lw in line_words:
                        if merged_text:
                            merged_text += " "
                        merged_text += lw['text']
                        min_x0 = min(min_x0, lw['bbox'][0])
                        min_y0 = min(min_y0, lw['bbox'][1])
                        max_x1 = max(max_x1, lw['bbox'][2])
                        max_y1 = max(max_y1, lw['bbox'][3])
                    text_blocks.append({
                        'text': merged_text,
                        'bbox': [
                            int(min_x0), int(min_y0),
                            int(max_x1), int(max_y1)
                        ]
                    })
            else:
                text_blocks = self.ocr_image(img)

            return img, text_blocks
        finally:
            doc.close()

    def parse_pdf(self, pdf_path, page_num=0):
        doc = pymupdf.open(pdf_path)
        try:
            if page_num >= len(doc):
                page_num = 0

            page = doc.load_page(page_num)

            # Lower-memory PDF rendering for Render.
            target_dpi = 200
            zoom = target_dpi / 72.0
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img_bytes = pix.tobytes("jpg", jpg_quality=85)
            file_bytes = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

            if img is None:
                raise ValueError("Failed to convert PDF page to image")

            # Prevent very large P&ID pages from exhausting Render RAM.
            max_dim = 3000
            h, w = img.shape[:2]

            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(
                    img,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_AREA
                )
                coord_scale = scale
            else:
                coord_scale = 1.0

            text_blocks = []
            words = page.get_text("words")

            if words:
                temp_lines = {}

                for w in words:
                    x0, y0, x1, y1, word, block_idx, line_idx, _ = w

                    rx0 = x0 * zoom * coord_scale
                    ry0 = y0 * zoom * coord_scale
                    rx1 = x1 * zoom * coord_scale
                    ry1 = y1 * zoom * coord_scale

                    key = (block_idx, line_idx)

                    if key not in temp_lines:
                        temp_lines[key] = []

                    temp_lines[key].append({
                        'text': word,
                        'bbox': [rx0, ry0, rx1, ry1]
                    })

                for key, line_words in temp_lines.items():
                    line_words.sort(key=lambda item: item['bbox'][0])

                    merged_text = ""
                    min_x0 = float('inf')
                    min_y0 = float('inf')
                    max_x1 = float('-inf')
                    max_y1 = float('-inf')

                    for lw in line_words:
                        if merged_text:
                            merged_text += " "

                        merged_text += lw['text']
                        min_x0 = min(min_x0, lw['bbox'][0])
                        min_y0 = min(min_y0, lw['bbox'][1])
                        max_x1 = max(max_x1, lw['bbox'][2])
                        max_y1 = max(max_y1, lw['bbox'][3])

                    text_blocks.append({
                        'text': merged_text,
                        'bbox': [
                            int(min_x0),
                            int(min_y0),
                            int(max_x1),
                            int(max_y1)
                        ]
                    })
            else:
                text_blocks = self.ocr_image(img)

            return img, text_blocks

        finally:
            doc.close()

    def ocr_image(self, img):
        # Run OCR directly on the image to avoid an extra disk file and memory copy.
        reader = self.get_ocr_reader()
        ocr_results = reader.readtext(img)

        text_blocks = []
        for bbox, text_value, prob in ocr_results:
            if prob > 0.25:
                x0 = int(min(pt[0] for pt in bbox))
                y0 = int(min(pt[1] for pt in bbox))
                x1 = int(max(pt[0] for pt in bbox))
                y1 = int(max(pt[1] for pt in bbox))
                text_blocks.append({
                    'text': text_value.strip(),
                    'bbox': [x0, y0, x1, y1]
                })

        return text_blocks

    def detect_symbols(self, img, text_blocks):
        H, W, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Adaptive thresholding to capture clean drawing contours
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 15, 4
        )

        symbols = []
        mapped_centers = []

        # Tag pattern regex (prefix followed by optional code)
        tag_prefixes = [
            'SDV', 'RV', 'CV', 'XV', 'ZSO', 'ZSC', 'ZIO', 'ZIC', 'XY', 'PI', 'PT', 'PG', 'TG', 
            'FIC', 'FCV', 'FY', 'BE', 'BZ', 'PCV', 'PRV', 'XI', 'TE', 'FT', 'TT', 'LT', 'LG', 
            'ZLO', 'DDL', 'RO', 'CL', 'V', 'HV', 'LV', 'PV', 'FV', 'LALL', 'LSLL', 'LAHH', 'LSHH', 
            'SOV', 'FC', 'FE', 'INS'
        ]
        prefix_pattern = re.compile(
            r'\b(' + '|'.join(tag_prefixes) + r')\b', 
            re.IGNORECASE
        )

        # 1. Group text blocks that are vertically or horizontally close (stacked P&ID tag components)
        grouped_text_blocks = []
        used_indices = set()
        
        # Pre-process text blocks: combine nearby texts to reconstruct tags
        for i, tb1 in enumerate(text_blocks):
            if i in used_indices:
                continue
            txt1 = tb1['text']
            bx1 = tb1['bbox']
            
            merged_text = txt1
            min_x0, min_y0, max_x1, max_y1 = bx1
            
            # Look for adjacent/stacked labels
            for j, tb2 in enumerate(text_blocks):
                if j == i or j in used_indices:
                    continue
                txt2 = tb2['text']
                bx2 = tb2['bbox']
                
                # Check closeness horizontally or vertically
                x_dist = min(abs(bx1[2] - bx2[0]), abs(bx2[2] - bx1[0]))
                y_dist = min(abs(bx1[3] - bx2[1]), abs(bx2[3] - bx1[1]))
                x_overlap = min(bx1[2], bx2[2]) - max(bx1[0], bx2[0])
                
                # Check vertical stack (typical inside bubbles)
                is_stacked = x_overlap > -10 and 0 <= (bx2[1] - bx1[3]) < 30
                # Check inline
                is_inline = y_dist < 15 and 0 <= x_dist < 40
                
                if is_stacked or is_inline:
                    merged_text = f"{merged_text}-{txt2}"
                    min_x0 = min(min_x0, bx2[0])
                    min_y0 = min(min_y0, bx2[1])
                    max_x1 = max(max_x1, bx2[2])
                    max_y1 = max(max_y1, bx2[3])
                    used_indices.add(j)
            
            grouped_text_blocks.append({
                'text': merged_text,
                'bbox': [min_x0, min_y0, max_x1, max_y1]
            })
            used_indices.add(i)

        # Check if YOLO symbol model is available
        symbol_model = self.get_symbol_model()
        yolo_success = False

        if symbol_model is not None:
            try:
                results = symbol_model.predict(source=img, conf=0.15, device="cpu", verbose=False)
                res = results[0]
                symbol_id_counter = 0
                
                for box in res.boxes:
                    xmin, ymin, xmax, ymax = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    class_id = int(box.cls[0])
                    cls_name = symbol_model.names[class_id]
                    
                    cx = int((xmin + xmax) / 2)
                    cy = int((ymin + ymax) / 2)
                    radius = int(max(xmax - xmin, ymax - ymin) / 2)
                    
                    # 160x160 box centered
                    xmin_s = max(0, cx - 80)
                    xmax_s = min(W, cx + 80)
                    ymin_s = max(0, cy - 80)
                    ymax_s = min(H, cy + 80)
                    
                    # Try to match with an OCR tag
                    matched_tag = None
                    min_dist = float('inf')
                    
                    for tb in grouped_text_blocks:
                        tx = tb['text']
                        bx = tb['bbox']
                        
                        m = prefix_pattern.search(tx)
                        if m:
                            parts = [p.strip() for p in tx.split('-') if p.strip()]
                            clean_tag = "-".join(parts)
                            
                            has_digit = any(c.isdigit() for c in clean_tag)
                            if len(clean_tag) > 25:
                                continue
                            if not has_digit and len(clean_tag) > 5:
                                continue
                                
                            tx_cx = (bx[0] + bx[2]) / 2
                            tx_cy = (bx[1] + bx[3]) / 2
                            
                            dist = np.hypot(cx - tx_cx, cy - tx_cy)
                            # OCR tag should be relatively close to the symbol center
                            if dist < 120 and dist < min_dist:
                                min_dist = dist
                                matched_tag = clean_tag.upper()
                    
                    if matched_tag:
                        tag = matched_tag
                    else:
                        tag = cls_name.upper()
                        
                    # Filter out duplicates
                    duplicate = False
                    for s in symbols:
                        if np.hypot(cx - s['center'][0], cy - s['center'][1]) < 40:
                            duplicate = True
                            break
                    if duplicate:
                        continue
                        
                    symbols.append({
                        'id': f"obj_{symbol_id_counter}",
                        'tag': tag,
                        'type': cls_name,
                        'class_id': class_id,
                        'bbox': [int(xmin_s), int(ymin_s), int(xmax_s), int(ymax_s)],
                        'center': [cx, cy],
                        'radius': radius
                    })
                    mapped_centers.append((cx, cy))
                    symbol_id_counter += 1
                
                yolo_success = True
            except Exception as e:
                print("Error during YOLO symbol detection prediction:", e)
                # Fallback to contours
                symbols = []
                mapped_centers = []

        if not yolo_success:
            # 2. Extract contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 3. Associate tags with shapes
            symbol_id_counter = 0
            
            # Define component classification helper
            def get_class_info(tag_str):
                tag_upper = tag_str.upper()
                
                # Class 2: Circular loop
                if any(p in tag_upper for p in ['RV-', 'CL-', 'PRV-', 'SDV-']):
                    return 2, 'Circular loop'
                # Class 1: Control Valve
                elif any(p in tag_upper for p in ['FCV-', 'TCV-', 'PCV-', 'LCV-', 'CV-', '-CV']):
                    return 1, 'Control Valve'
                # Class 0: Valve
                elif any(p in tag_upper for p in ['XV-', 'HV-', 'GH-', 'AB-', 'WX-', 'ST-', 'UV-']):
                    return 0, 'Valve'
                # Class 3: Spectacle Blind
                elif 'SB-' in tag_upper or 'SPECTACLE' in tag_upper:
                    return 3, 'Spectacle Blind'
                # Class 4: Inline Mixer
                elif 'CS' == tag_upper or 'MX-' in tag_upper:
                    return 4, 'Inline Mixer'
                # Class 4: Undefined
                elif 'INS' in tag_upper:
                    return 4, 'Undefined'
                # Class 5: Instrument (default for gauges and loops)
                else:
                    return 5, 'Instrument'
            
            # Loop through reconstructed tags and map them to nearest contour shapes
            for tb in grouped_text_blocks:
                tx = tb['text']
                bx = tb['bbox']
                
                m = prefix_pattern.search(tx)
                if m:
                    # Reconstruct tag cleanly: e.g. "PT-1112B-01"
                    parts = [p.strip() for p in tx.split('-') if p.strip()]
                    clean_tag = "-".join(parts)
                    
                    # Filter out long notes blocks and false positive text blocks
                    has_digit = any(c.isdigit() for c in clean_tag)
                    if len(clean_tag) > 25:
                        continue
                    if not has_digit and len(clean_tag) > 5:
                        continue
                    
                    tx_cx = (bx[0] + bx[2]) / 2
                    tx_cy = (bx[1] + bx[3]) / 2
                    
                    # Find nearest graphical contour
                    nearest_contour = None
                    min_dist = float('inf')
                    for c in contours:
                        area = cv2.contourArea(c)
                        if area < 100:  # skip noise
                            continue
                        # Calculate center of contour
                        M = cv2.moments(c)
                        if M["m00"] == 0:
                            continue
                        ccx = int(M["m10"] / M["m00"])
                        ccy = int(M["m01"] / M["m00"])
                        
                        dist = np.hypot(ccx - tx_cx, ccy - tx_cy)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_contour = c
                    
                    cx, cy = int(tx_cx), int(tx_cy)
                    if nearest_contour is not None and min_dist < 100:
                        # Use contour center
                        M = cv2.moments(nearest_contour)
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    
                    # Filter out overlapping detections
                    duplicate = False
                    for mcx, mcy in mapped_centers:
                        if np.hypot(cx - mcx, cy - mcy) < 60:
                            duplicate = True
                            break
                    if duplicate:
                        continue
                    
                    # Get class
                    class_id, comp_name = get_class_info(clean_tag)
                    
                    # Bounding box: exactly 160x160 centered at (cx, cy)
                    xmin = max(0, cx - 80)
                    xmax = min(W, cx + 80)
                    ymin = max(0, cy - 80)
                    ymax = min(H, cy + 80)
                    
                    symbols.append({
                        'id': f"obj_{symbol_id_counter}",
                        'tag': clean_tag.upper(),
                        'type': comp_name,
                        'class_id': class_id,
                        'bbox': [xmin, ymin, xmax, ymax],
                        'center': [cx, cy],
                        'radius': 80
                    })
                    mapped_centers.append((cx, cy))
                    symbol_id_counter += 1
            
            # 4. Pure Geometric Search for Untagged Components (e.g. manual valves or spectacle blinds)
            for c in contours:
                area = cv2.contourArea(c)
                perimeter = cv2.arcLength(c, True)
                if perimeter == 0 or area < 200:
                    continue
                
                # Calculate moments
                M = cv2.moments(c)
                if M["m00"] == 0:
                    continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Check if this contour center is close to any already mapped tag center
                already_mapped = False
                for mcx, mcy in mapped_centers:
                    if np.hypot(cx - mcx, cy - mcy) < 70:
                        already_mapped = True
                        break
                if already_mapped:
                    continue
                    
                # Classify contour purely on geometry
                solidity = area / cv2.contourArea(cv2.convexHull(c)) if cv2.contourArea(cv2.convexHull(c)) > 0 else 0
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                
                x_b, y_b, w_b, h_b = cv2.boundingRect(c)
                ar = max(w_b / h_b, h_b / w_b) if h_b > 0 and w_b > 0 else 1
                
                class_id = None
                comp_name = None
                
                # Circle test -> Class 5: Instrument
                if circularity > 0.75 and 20 < w_b < 120:
                    class_id, comp_name = 5, 'Instrument'
                # Bow-tie test -> Class 0: Valve
                elif 0.45 < solidity < 0.70 and 1.2 < ar < 2.5 and 200 < area < 2500:
                    class_id, comp_name = 0, 'Valve'
                # Figure-8 test -> Class 3: Spectacle Blind
                elif 0.70 < solidity < 0.88 and 1.6 < ar < 2.4 and 150 < area < 1000:
                    class_id, comp_name = 3, 'Spectacle Blind'
                
                if class_id is not None:
                    # 160x160 box centered
                    xmin = max(0, cx - 80)
                    xmax = min(W, cx + 80)
                    ymin = max(0, cy - 80)
                    ymax = min(H, cy + 80)
                    
                    symbols.append({
                        'id': f"obj_{symbol_id_counter}",
                        'tag': 'UNDEFINED',
                        'type': comp_name,
                        'class_id': class_id,
                        'bbox': [xmin, ymin, xmax, ymax],
                        'center': [cx, cy],
                        'radius': 80
                    })
                    mapped_centers.append((cx, cy))
                    symbol_id_counter += 1

        # Sort symbols by coordinates to make Excel sheet tidy
        symbols.sort(key=lambda s: (s['center'][1], s['center'][0]))
        # Re-assign clean sequential object IDs
        for idx, s in enumerate(symbols):
            s['id'] = f"obj_{idx}"

        # Release large intermediate OpenCV arrays before returning.
        if 'contours' in locals():
            del contours
        del gray, binary
        return symbols, grouped_text_blocks

    def get_yolo_model(self):
        if self.yolo_model is None and os.path.exists(self.yolo_model_path):
            try:
                # Import Ultralytics only when YOLO tracing is actually requested.
                from ultralytics import YOLO
                self.yolo_model = YOLO(self.yolo_model_path)
            except Exception as e:
                print("Error loading YOLO model:", e)
                self.yolo_model = None
        return self.yolo_model

    def trace_connections(self, img, symbols, text_blocks):
        H, W, _ = img.shape
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 15, 4
        )

        # Use YOLO model pipeline segmentation to guide pathfinding.
        yolo_model = self.get_yolo_model()
        if yolo_model is not None:
            try:
                results = yolo_model.predict(source=img, conf=0.20, device="cpu", verbose=False)
                res = results[0]
                yolo_mask = np.zeros((H, W), dtype=np.uint8)
                if hasattr(res, "masks") and res.masks is not None and hasattr(res.masks, "data"):
                    for m in res.masks.data:
                        mask = (m.cpu().numpy() * 255).astype(np.uint8)
                        mask_resized = cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST)
                        yolo_mask = cv2.bitwise_or(yolo_mask, mask_resized)
                
                if yolo_mask.max() > 0:
                    # Dilate YOLO mask slightly to bridge gaps and intersect with high-res lines
                    yolo_mask_dilated = cv2.dilate(yolo_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
                    binary = cv2.bitwise_and(binary, yolo_mask_dilated)
            except Exception as e:
                print("Error during YOLO pipeline segmentation:", e)

        for tb in text_blocks:
            x0, y0, x1, y1 = tb['bbox']
            cv2.rectangle(binary, (max(0, x0-3), max(0, y0-3)), (min(W, x1+3), min(H, y1+3)), 0, -1)

        for s in symbols:
            x0, y0, x1, y1 = s['bbox']
            cv2.rectangle(binary, (x0 + 4, y0 + 4), (x1 - 4, y1 - 4), 0, -1)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(binary, kernel, iterations=1)

        ds_factor = 2
        grid_h, grid_w = H // ds_factor, W // ds_factor
        grid = cv2.resize(dilated, (grid_w, grid_h), interpolation=cv2.INTER_NEAREST)

        connections = []
        conn_id = 0

        # Run connections tracing for close component pairs
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                s1 = symbols[i]
                s2 = symbols[j]

                c1 = s1['center']
                c2 = s2['center']
                center_dist = np.hypot(c1[0] - c2[0], c1[1] - c2[1])
                
                # Check maximum connection distance: skip very distant ones
                if center_dist > 600:
                    continue

                bx1 = [val // ds_factor for val in s1['bbox']]
                bx2 = [val // ds_factor for val in s2['bbox']]

                starts = []
                for y in range(max(0, bx1[1]-1), min(grid_h, bx1[3]+2)):
                    starts.append((bx1[0]-1, y))
                    starts.append((bx1[2]+1, y))
                for x in range(max(0, bx1[0]-1), min(grid_w, bx1[2]+2)):
                    starts.append((x, bx1[1]-1))
                    starts.append((x, bx1[3]+2))
                
                starts = [(x, y) for (x, y) in starts if 0 <= x < grid_w and 0 <= y < grid_h and grid[y, x] > 0]
                
                if not starts:
                    continue

                target_x0, target_y0, target_x1, target_y1 = bx2

                path = self._bfs_grid(grid, starts, target_x0, target_y0, target_x1, target_y1, max_depth=int(center_dist / ds_factor * 1.8))
                
                if path:
                    orig_path = [[pt[0] * ds_factor, pt[1] * ds_factor] for pt in path]
                    conn_type = self._classify_connection(binary, orig_path)
                    
                    associated_label = ""
                    path_points = np.array(orig_path)
                    for tb in text_blocks:
                        tx = tb['text']
                        bx = tb['bbox']
                        if re.search(r'\d+.*-.*-.*-\d+', tx) or re.search(r'\b\d+\s*[-]\s*[A-Z]\s*[-]', tx):
                            tx_cx = (bx[0] + bx[2]) / 2
                            tx_cy = (bx[1] + bx[3]) / 2
                            dists = np.hypot(path_points[:, 0] - tx_cx, path_points[:, 1] - tx_cy)
                            if np.min(dists) < 150:
                                associated_label = tx
                                break

                    connections.append({
                        'id': f"conn_{conn_id}",
                        'source': s1['id'],
                        'source_tag': s1['tag'],
                        'target': s2['id'],
                        'target_tag': s2['tag'],
                        'type': conn_type,
                        'label': associated_label,
                        'path': orig_path
                    })
                    conn_id += 1

        # Release large connection-tracing arrays before returning.
        del gray, binary, dilated, grid
        return connections

    def _bfs_grid(self, grid, starts, tx0, ty0, tx1, ty1, max_depth=800):
        h, w = grid.shape
        queue = []
        visited = set()

        for pt in starts:
            queue.append((pt[0], pt[1], []))
            visited.add((pt[0], pt[1]))

        depth = 0
        while queue and depth < max_depth:
            next_level = []
            for cx, cy, path in queue:
                if (tx0 - 2 <= cx <= tx1 + 2) and (ty0 - 2 <= cy <= ty1 + 2):
                    return path + [[cx, cy]]

                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if (nx, ny) not in visited and grid[ny, nx] > 0:
                            visited.add((nx, ny))
                            next_level.append((nx, ny, path + [[cx, cy]]))
            queue = next_level
            depth += 1

        return None

    def _classify_connection(self, binary, path):
        H, W = binary.shape
        on_pixels = 0
        transitions = 0
        prev_val = 0

        sample_step = max(1, len(path) // 50)
        sampled_path = path[::sample_step]

        for pt in sampled_path:
            x, y = int(pt[0]), int(pt[1])
            if 0 <= x < W and 0 <= y < H:
                val = 1 if binary[y, x] > 0 else 0
                on_pixels += val
                if val != prev_val:
                    transitions += 1
                prev_val = val

        on_ratio = on_pixels / len(sampled_path) if sampled_path else 0
        
        if on_ratio > 0.80:
            return 'Process Line'
        elif on_ratio > 0.25:
            if transitions >= 4:
                return 'Electric Signal'
            else:
                return 'Pneumatic Signal'
        else:
            return 'Process Line'

    def generate_excel(self, symbols, connections, output_path):
        """
        Generates Excel sheet matching user's expected columns:
        Object-ID, Class-ID, Component Name, Item Label, xmin,xmax,ymin,ymax
        """
        excel_data = []
        for s in symbols:
            # Extract box
            xmin, ymin, xmax, ymax = s['bbox']
            # Sequential numeric ID
            obj_numeric_id = int(s['id'].split('_')[1])
            
            excel_data.append({
                'Object-ID': obj_numeric_id,
                'Class-ID': s['class_id'],
                'Component Name': s['type'],
                'Item Label': s['tag'],
                'xmin,xmax,ymin,ymax': f"{xmin},{xmax},{ymin},{ymax}"
            })
            
        df = pd.DataFrame(excel_data)

        # Write to excel with custom styling matching professional sheet
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='P&ID Component Inventory', index=False)

            workbook = writer.book
            worksheet = writer.sheets['P&ID Component Inventory']
            
            # Format styles
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#FFFFFF',
                'font_color': '#000000',
                'border': 1
            })
            
            cell_format = workbook.add_format({
                'border': 1,
                'valign': 'vcenter'
            })

            # Headers styling
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Cell borders
            for row in range(len(df)):
                for col in range(len(df.columns)):
                    val = df.iloc[row, col]
                    worksheet.write(row + 1, col, val, cell_format)
            
            # Width auto-fit
            for idx, col in enumerate(df):
                series = df[col]
                max_len = max(
                    series.astype(str).map(len).max(),
                    len(str(col))
                ) + 4
                worksheet.set_column(idx, idx, max_len)

        print(f"Excel workbook generated successfully at {output_path}")
