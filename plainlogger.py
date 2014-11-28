import datetime
import logging
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ClientFactory
import peewee
import sys

ADDRESS = '10.100.0.4'
DATABASE_FILE = 'planes.db'
HOME_LAT = 48.9036812
HOME_LON = 9.1475182
PORT = 30003

logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.INFO)

# http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points
from math import radians, cos, sin, asin, sqrt
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6367 * c
    return km

database = peewee.SqliteDatabase(DATABASE_FILE)
database.connect()

class BaseModel(peewee.Model):
    class Meta:
        database = database

class Plane(BaseModel):
    date = peewee.DateField()
    lcao = peewee.CharField()
    callsign = peewee.CharField()

    class Meta:
        database = database

database.create_tables([Plane], True)

# http://www.homepages.mcb.net/bones/SBS/Article/Barebones42_Socket_Data.htm
class Field:
    message_type = 0
    transmission_type = 1
    session_id = 2
    aircraft_id = 3
    hexident = 4
    flight_id = 5
    date_message_generated = 6
    time_message_generated = 7
    date_message_logged = 8
    time_message_logged = 9
    callsign = 10
    altitude = 11
    ground_speed = 12
    track = 13
    latitude = 14
    longitude = 15
    vertical_rate = 16
    squawk = 17
    alert = 18
    emergency = 19
    spi = 20
    is_on_ground = 21


class Sbs1(Protocol):
    def dataReceived(self, data):
        lines = data.strip().split('\n')
        for line in lines:
            message = line.split(',')
            try:
                lcao = message[Field.hexident]
                if message[Field.message_type] == 'MSG' and message[Field.transmission_type] == '1':
                    callsign = message[Field.callsign]
                    date = message[Field.date_message_generated]
                    number = Plane.select().where((Plane.lcao == lcao) & (Plane.callsign == callsign) & (Plane.date == date)).count()
                    if number == 0:
                        logging.info("Registered new plain: ICAO: %s, Callsign: %s" % (lcao, callsign))
                        plane = Plane(lcao=lcao, callsign=callsign, date=date)
                        plane.save()
                elif message[Field.message_type] == 'MSG' and message[Field.transmission_type] == '3':
                    lon = float(message[Field.longitude])
                    lat = float(message[Field.latitude])
                    distance = haversine(HOME_LON, HOME_LAT, lon, lat)
                    logging.debug("ICAO: %s, LON: %s, LAT: %s" % (lcao, lon, lat))
                    logging.debug("ICAO: %s, distance: %s" % (lcao, distance))
            except (ValueError, IndexError):
                logging.debug("Skipping invalid message: %s", line)


class Sbs1ClientFactory(ClientFactory):
    def startedConnecting(self, connector):
        logging.debug('Started to connect.')

    def buildProtocol(self, addr):
        logging.debug('Connected.')
        return Sbs1()

    def clientConnectionLost(self, connector, reason):
        logging.error('Lost connection.  Reason: %s', reason)

    def clientConnectionFailed(self, connector, reason):
        logging.error('Connection failed. Reason: %s', reason)


reactor.connectTCP(ADDRESS, PORT, Sbs1ClientFactory())
reactor.run()
