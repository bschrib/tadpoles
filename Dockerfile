FROM ubuntu:trusty
MAINTAINER twneale@gmail.com

RUN apt-get update && apt-get upgrade -y

RUN apt-get install -qyy \
    -o APT::Install-Recommends=false -o APT::Install-Suggests=false \
    python-virtualenv python3.4-dev python3-setuptools \
    python3-pip xvfb firefox python3-lxml curl

RUN pip3 install selenium xvfbwrapper pyyaml requests

WORKDIR /app
ADD "py/*" /app/
RUN curl -L https://github.com/mozilla/geckodriver/releases/download/v0.19.1/geckodriver-v0.19.1-linux64.tar.gz | tar xz -C /usr/local/bin
CMD ["geckodriver", "--host", "0.0.0.0"]
CMD ["python3.4", "/app/app.py"]
