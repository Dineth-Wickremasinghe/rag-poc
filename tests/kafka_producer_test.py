import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kafka import KafkaProducer

from config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC

producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

producer.send(KAFKA_TOPIC, b"Hello Kafka")
producer.flush()

print("Message sent successfully!")
