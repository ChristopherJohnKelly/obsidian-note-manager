FROM python:3.12-slim
WORKDIR /app
COPY apps/copilot_ui apps/copilot_ui
COPY packages packages
RUN pip install -r apps/copilot_ui/requirements.txt
CMD ["chainlit", "run", "apps/copilot_ui/app.py", "--host", "0.0.0.0"]
