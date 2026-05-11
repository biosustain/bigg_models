FROM python:3.11
ENV PYTHONUNBUFFERED=1
RUN mkdir /app
WORKDIR /app

# Install dependencies

# RUN wget https://github.com/draeger-lab/ModelPolisher/releases/download/1.7/ModelPolisher-1.7.jar

#RUN apt-get update && apt-get install -y \
#  libxml2-dev postgresql-client openjdk-17-jre
RUN apt-get update && apt-get install -y \
  libxml2-dev postgresql-client


COPY requirements.txt /app/
RUN pip install -r requirements.txt

RUN git clone https://github.com/biosustain/biggr_maps.git biggr_maps
WORKDIR /app/biggr_maps/
# RUN git pull && git reset --hard 54c6d88
RUN python setup.py install
WORKDIR /app

RUN git clone https://github.com/biosustain/cobradb.git cobradb
WORKDIR /app/cobradb
# RUN git pull && git reset --hard 313ce67
RUN python setup.py install
WORKDIR /app

RUN apt-get install -y nodejs npm
RUN npm install -g sass
RUN npm install bootstrap@5.3.7

COPY biggr_models/ /app/biggr_models/
COPY bin/ /app/bin/
COPY scripts/ /app/scripts/
COPY pytest.ini /app/
COPY setup.cfg /app/
COPY setup.py /app/

RUN sass ./biggr_models/scss/custom.scss ./biggr_models/static/css/custom.css

RUN cp node_modules/bootstrap/dist/js/bootstrap.bundle.min.js biggr_models/static/js/

RUN python setup.py install

#CMD ["python", "-m", "biggr_models.server", "--port=8910", "--processes=6"]
CMD ["bin/server-entrypoint.sh"]
