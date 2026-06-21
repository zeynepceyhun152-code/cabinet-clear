import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import numpy as np
import io
import base64
import os

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

clarity_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
])

_model = None

def load_model():
    model = models.resnet18(weights=None)
    model.fc = nn.Sequential(
        nn.Linear(model.fc.in_features, 1),
        nn.Sigmoid()
    )
    model_path = os.path.join(os.path.dirname(__file__), "clarity_model.pth")
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    return model.to(device)

def get_model():
    global _model
    if _model is None:
        _model = load_model()
    return _model

def check_clarity(image_bytes: bytes) -> dict:
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
    from pytorch_grad_cam.utils.image import show_cam_on_image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    model = get_model()

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_resized = img.resize((224, 224))
    img_array = np.array(img_resized).astype(np.float32) / 255.0

    tensor = clarity_transform(img).unsqueeze(0).to(device)

    with torch.no_grad():
        score = model(tensor).item()

    is_clear = score > 0.5
    confidence_pct = round(score * 100 if is_clear else (1 - score) * 100, 1)

    target_layers = [model.layer4[-1]]
    cam = GradCAM(model=model, target_layers=target_layers)
    grayscale_cam = cam(input_tensor=tensor, targets=[ClassifierOutputTarget(0)])[0]
    visualization = show_cam_on_image(img_array, grayscale_cam, use_rgb=True)

    buf = io.BytesIO()
    plt.figure(figsize=(4,4))
    plt.imshow(visualization)
    plt.axis('off')
    plt.tight_layout(pad=0)
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close()
    buf.seek(0)
    heatmap_b64 = base64.b64encode(buf.read()).decode()

    return {
        "is_clear": is_clear,
        "confidence_pct": confidence_pct,
        "raw_score": round(score, 4),
        "heatmap_base64": heatmap_b64,
        "message": f"Image is {'clear' if is_clear else 'unclear'} ({confidence_pct}% confident)"
    }
