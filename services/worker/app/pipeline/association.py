from app.pipeline.geometry import Detection
from app.tracking.tracker import TrackedVehicle


def associate_plates(
    vehicles: list[TrackedVehicle],
    plates: list[Detection],
) -> list[tuple[TrackedVehicle, Detection]]:
    """Assign each plate to at most one vehicle using containment, nearby rear-plate, IoU, and distance."""
    pairs: list[tuple[TrackedVehicle, Detection, float]] = []
    for plate in plates:
        px, py = plate.bounding_box.center
        best: tuple[TrackedVehicle, float, bool] | None = None
        for vehicle in vehicles:
            box = vehicle.detection.bounding_box
            pad_x, pad_y = box.width * 0.12, box.height * 0.12
            contained = (
                box.x1 - pad_x <= px <= box.x2 + pad_x and box.y1 - pad_y <= py <= box.y2 + pad_y
            )
            near = (
                box.x1 - box.width * 0.28 <= px <= box.x2 + box.width * 0.28
                and box.y1 - box.height * 0.15 <= py <= box.y2 + box.height * 0.40
            )
            iou = plate.bounding_box.iou(box)
            vx, vy = box.center
            dist = ((px - vx) ** 2 + (py - vy) ** 2) ** 0.5
            diag = (box.width**2 + box.height**2) ** 0.5 or 1.0
            score = 0.0
            if contained:
                score += 3.0
            elif near:
                score += 2.0
            score += iou * 2.0
            score += max(0.0, 1.0 - dist / diag)
            score += 0.2 * plate.confidence + 0.1 * vehicle.detection.confidence
            in_lower = py >= box.y1 + box.height * 0.35
            if in_lower:
                score += 0.4
            if best is None or score > best[1]:
                best = (vehicle, score, contained or near)
        if best and best[1] >= 1.5 and best[2]:
            pairs.append((best[0], plate, best[1]))
    pairs.sort(key=lambda item: item[2], reverse=True)
    used_vehicles: set[int] = set()
    used_plates: set[int] = set()
    assigned: list[tuple[TrackedVehicle, Detection]] = []
    for vehicle, plate, _score in pairs:
        vid = vehicle.track_id
        pid = id(plate)
        if vid in used_vehicles or pid in used_plates:
            continue
        used_vehicles.add(vid)
        used_plates.add(pid)
        assigned.append((vehicle, plate))
    return assigned
