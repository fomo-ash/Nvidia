FROM python:3.12.8-slim
WORKDIR /app
COPY app.py traffic.py ./
USER 65532:65532
EXPOSE 8080
CMD ["python", "app.py"]
