from flask import Flask, request;
import urllib3;
import time;
import hashlib;
import json;
import threading;
import pymongo;
import json;
import logging;
from bson import json_util;
from typing import Callable;
from logging.handlers import RotatingFileHandler;
from logging.config import dictConfig;
import logtail;

dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'default'
        },
        'size-rotate': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': './castornaut.log',
            'maxBytes': 100,
            'backupCount': 5,
            'formatter': 'default',
        },
        'logtail' :{
            'class': 'logtail.LogtailHandler',
            'source_token': '5N8MPSvo6UG87HxmnzKHrEH7',
            'formatter': 'default',
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'size-rotate', 'logtail']
    }
});

server = Flask(__name__);
logger = server.logger;

@server.route('/')
def hello() -> str:
    return 'You\'ve reached castornaut';


#TODO: Create interfaces fro different sources: spotify, apple, etc https://www.scaler.com/topics/interface-in-python/
@server.route('/podcasts/trending', methods=['GET'])
def get_trending_podcasts() -> str:
    start_index: int = int(request.args.get('startIndex'));
    end_index: int = int(request.args.get('endIndex'));
    
    #get podcast collection from mongoDB
    try :
        mongo_client : pymongo.client = initialize_mongo_client();
        db = mongo_client['castornaut'];
        table_podcasts = db['podcasts'];
        collection_trending_podcasts = table_podcasts['trending'];
        
        #check if we have enough data cache to return
        if collection_trending_podcasts.count_documents({}) > end_index:
            logger.log(logging.INFO,'<< Returning Cached >>');
            cachedPodcasts: list = [];
            for x in collection_trending_podcasts.find().skip(start_index).limit(end_index - start_index):
                cachedPodcasts.append(json.loads(json_util.dumps(x)));
            return cachedPodcasts;
        #if it doesn't, make an 3rd party api call to get the data and cache it
        else:
            logger.log(logging.INFO,'<< Making API Call >>');
            podcastsFromApi: str = get_podcasts_from_api(mongo_client, start_index, end_index);
            deserialized_podcasts: list = json.loads(podcastsFromApi);
            
            # start a thread to cache the podcasts
            start_thread(cache_podcasts, 'cache_podcasts', [collection_trending_podcasts, deserialized_podcasts['feeds']]);
            return deserialized_podcasts['feeds'];
    except Exception as e: 
        return 'Exception occured: ' + str(e);


def get_podcasts_from_api(mongo_client: pymongo.MongoClient, startindex: int, endindex: int) -> str:
    http = urllib3.PoolManager();
    response = http.request(
        'GET', 
        'https://api.podcastindex.org/api/1.0/podcasts/trending', 
        fields={'max': f'{endindex}'}, 
        headers=create_request_header());
    
    if response.status == 200:
        logger.log(logging.INFO,'<< Received date>>')
        return response.data;
    else:
        logger.log(logging.INFO,'<< Received error ' + str(response.status) + '>>')
        return Exception('Error: ' + str(response.status));


def initialize_mongo_client() -> pymongo.MongoClient:
    #connect to the mongo db
    return pymongo.MongoClient("mongodb+srv://castornautadmin:Castornaut2023@cluster0.okufuf1.mongodb.net/?retryWrites=true&w=majority");


def create_request_header() -> dict:
    apiKey: str = "AZC7VAQWWTJVNAUEUFMK";
    apiSecret: str = "4HTK6tsh24kurQzdZ9KmVRz76MxyThrG4YR8SUPQ";
    currentUnixTime: str = str(int(time.time()));
    # our hash here is the api key + secret + time 
    data_to_hash: str = apiKey + apiSecret + currentUnixTime;
    # which is then sha-1'd
    sha1: str = hashlib.sha1(data_to_hash.encode()).hexdigest();

    return {
      "X-Auth-Date": str(currentUnixTime),
      "X-Auth-Key": apiKey,
      "Authorization": sha1,
      "User-Agent": "castornaut/0.1"
    };


def start_thread(func : Callable[..., None], name : str =None, args: list = []):
    threading.Thread(target=func, name=name, args=args).start();


def cache_podcasts(mongo_collection: pymongo.collection, json_podcasts: list):
    # save and update the trending podcasts
    # upsert being true leads to the intended update or insert behavior.
    logger.log(logging.INFO, f'<< Caching {len(json_podcasts)} podcasts >>');
    for podcast in json_podcasts:
        mongo_collection.update_one({'id': podcast['id']}, {'$set': podcast}, upsert=True);

# Run the server
if __name__ == "__main__":
    server.run(debug=True, port=5000);