FROM python:3.9-slim-buster
WORKDIR /app
COPY ./requirements.txt /app
RUN pip install -r requirements.txt
COPY . /app

# Expose the server port
EXPOSE 8080

# Calculate the number of worker processes based on the number of CPU cores
CMD ["gunicorn","--bind","0.0.0.0:8080","--workers","4","wsgi:server"]