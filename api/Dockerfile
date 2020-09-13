FROM python:3.8

WORKDIR /shortlinks

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8000

COPY . .

#RUN python3 ./src/installer.py
