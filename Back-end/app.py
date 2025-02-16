from flask import Flask, request, jsonify, Response
import json, torch, numpy as np
import os, sys, PIL
from models import model
from flask_cors import CORS
from werkzeug.utils import secure_filename
import base64 
from io import BytesIO

num_gpus = torch.cuda.device_count()
if num_gpus > 1:
    target_gpu = num_gpus - 2  # 마지막 디바이스 -1
else:
    target_gpu = 0  # GPU가 하나뿐이면 0번 사용

os.environ["CUDA_VISIBLE_DEVICES"] = str(target_gpu)
print(f"Using GPU: {os.environ['CUDA_VISIBLE_DEVICES']}")

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Flask Pose Model API"

@app.route("/predict", methods=["POST"])
def predict():
    # logging
    print("\n=== Request headers ===")
    print(request.headers)
    
    print("=== Request files ===")
    print(request.files)

    if 'file' not in request.files:
        return jsonify({"error": "Invalid input provided"}), 400
    
    file = request.files['file']

    # logging
    print("\n\n=== File info ===")
    print(f"Filename: {file.filename}")
    print(f"Content Type: {file.content_type}")
    print(f"File Size: {len(file.read())} bytes")
    file.seek(0) 

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    print(f"\n- 예측 시작 {file.filename} -")
    image = PIL.Image.open(file).convert("RGB")

    # 2개의 모델 객체 초기화
    stage1_model = model.PoseModel()
    stage2_model = model.DetailedPoseModel()

    # 자세 탐지 모델
    output1 = stage1_model.predict(image)
    # 공통 + 세부 자세 탐지 모델
    forResult = stage2_model._get_class_name(output1)
    output2 = stage2_model.predict(output1, image)

    # 파일 이름 처리 수정
    image_name = secure_filename(file.filename)
    # 이미지를 저장
    
    os.makedirs(f"./data/{forResult[0]}/",exist_ok=True)
    output2[1].save(f"./data/{forResult[0]}/{image_name}")
    
    
    result_data = {"posture": forResult[0], "abnormal_codes": []}
    for item in output2[0]:
        if item["type"] == "cls" and item["result"] == 1:
            result_data["abnormal_codes"].append({"code": item['class_name'], "message": f"오류코드: {item['class_name']}이(가) 검출되었습니다."})
        elif item["type"] == "obj" and "Normal" not in item["class_name"]:
            result_data["abnormal_codes"].append({"code": item['class_name'], "message": f"오류코드: {item['class_name']}이(가) 검출되었습니다."})
    
    if not result_data["abnormal_codes"]:
        result_data["status"] = "success"
        result_data["message"] = "The X-ray image was captured successfully"
    else:
        result_data["status"] = "error"
        result_data["message"] = "Retake recommended"
    

    # PIL Image -> BytesIO 변환
    image_stream = BytesIO()
    output2[1].save(image_stream, format="JPEG")  # JPEG 대신 PNG 등으로 변경 가능
    image_stream.seek(0)  # 스트림의 시작 위치로 이동

    # BytesIO -> Base64 인코딩
    encoded_image = base64.b64encode(image_stream.getvalue()).decode("utf-8")

    result_data["image"] = encoded_image  # JSON 데이터에 추가

    print(json.dumps(result_data, ensure_ascii=False, indent=4))
    
    return Response(
        json.dumps(result_data, ensure_ascii=False, indent=4),
        content_type="application/json; charset=utf-8"
)

if __name__ == "__main__":
    # 단일 서버로 실행할 때 port 번호는 여기에서 변경.
    # gunicorn 으로 실행할 때, port 번호는 gunicorn 명령어에서 변경.
    app.run(host="0.0.0.0", port=33333, threaded=True)
