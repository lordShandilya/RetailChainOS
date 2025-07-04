FROM python:3.9-slim

WORKDIR /

COPY requirement.txt .

RUN pip install --no-cache-dir -r requirement.txt

COPY . .

CMD [ "fastapi dev", "main.py" ]

