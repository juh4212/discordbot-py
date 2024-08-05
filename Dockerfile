# Dockerfile
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY requirements.txt .
COPY discordbot.py .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 실행
CMD ["python", "discordbot.py"]
