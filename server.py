import time
import paho.mqtt.client as mqtt
import firebase_admin
import struct
from firebase_admin import db

from credentials import MQTT_USER, MQTT_PWD

client = None
bigtimer_state = None

online_devs = set(['climbingclock_B8A7A1'])

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))

    client.subscribe("server/#")

def on_message(client, userdata, msg):
	if msg.topic == 'server/cmnd/clockinit':
		dev = msg.payload.decode('utf-8')

		online_devs.add(dev)
		publish_state(dev)

#		offset = get_clock_offset()
#		print(f'setting clock offset {offset} at {dev}')
#		client.publish(f'cmnd/{dev}/clock', offset)
	else:
		print(f'unknown topic: {msg.topic}')

def get_clock_offset():
	is_dst = time.daylight and time.localtime().tm_isdst > 0
	return -(time.altzone if is_dst else time.timezone)

def publish_state(dev):
	print(dev, bigtimer_state)

	state = bigtimer_state[:5]

	if state == 'CLOCK':
		d = bigtimer_state[5:13]
		offset = struct.unpack('<i', bytes.fromhex(d))[0]
		client.publish(f'cmnd/{dev}/clock', offset)
	elif state == 'TIMER':
		nums = []
		for i in range(3):
			d = bigtimer_state[5 + 16 * i:5 + 16 * (i + 1)]
			nums.append(struct.unpack('<q', bytes.fromhex(d))[0])

		numstr = ' '.join(str(x) for x in nums)
		client.publish(f'cmnd/{dev}/comptimer', numstr)
	elif state == 'NMBRS':
		nums = []
		colors = []

		for i in range(4):
			d = bigtimer_state[5 + 2 * i:5 + 2 * (i + 1)]
			nums.append(struct.unpack('<B', bytes.fromhex(d))[0])

		for i in range(4):
			c = bigtimer_state[13 + 6 * i:13 + 6 * (i + 1)]
			c = c[4:] + c[2:4] + c[:2]
			colors.append(c)

		numstr = ''.join(str(x) for x in nums)
		d_str = numstr + ' ' + ' '.join(x for x in colors)
		client.publish(f'cmnd/{dev}/numbers', d_str)

def bigtimer_listener(ev):
	global bigtimer_state
	bigtimer_state = ev.data

	for dev in online_devs:
		publish_state(dev)

def main():
	global client

	cred = firebase_admin.credentials.Certificate('firebase-admin.json')
	firebase_admin.initialize_app(cred, {
		'databaseURL': 'https://smart-abc-1893a-default-rtdb.firebaseio.com/'
	})

	client = mqtt.Client()
	client.username_pw_set(MQTT_USER, MQTT_PWD)

	client.on_connect = on_connect
	client.on_message = on_message

	listener = db.reference('bigtimer/state').listen(bigtimer_listener)

	client.connect("127.0.0.1", 1883, 60)
	client.loop_forever()

	listener.close()

if __name__ == '__main__':
	main()
