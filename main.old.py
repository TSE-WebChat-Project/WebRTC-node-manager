import asyncio
import threading
from os import environ as env
import websockets
import uuid
import simplegcd.Deployer as gcd
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Setup google cloud deployment
gcd.PROJECT = env['PROJECT']
gcd.ZONE = env['ZONE']

# Setup firebase
try:
    if env['ENVIRONMENT'] == 'development':
        cred = credentials.Certificate("service_account.json")
    else:
        cred = credentials.ApplicationDefault()
except KeyError:
    print("error")
    cred = credentials.ApplicationDefault()

firebase_admin.initialize_app(cred)
db = firestore.client()

# Firebase document
new_instances_ref = db.collection(u'new-instances').where(u'instance_group_name', u'==', u'management-node-deployer-1')
new_instance_callback = threading.Event()

connection_req_ref = db.collection(u'connection-req')
connection_req_callback = threading.Event()

# List of currently connected clients
CLIENTS = []
AUTHORIZED_CLIENTS = []


def on_new_instance_up(collection_snapshot, changes, read_time):
    for doc in changes:
        if doc.document.to_dict()['management_socket']:
            return
        print(f'Received document snapshot: {doc.document.id}')
        new_doc = doc.document.to_dict()
        # Authorise client to connect
        auth_dict = {"client_ip": new_doc['socket_address']}
        AUTHORIZED_CLIENTS.append(auth_dict)

        new_doc['management_socket'] = f"ws://{env['WEBSOCKET_IP']}:{env['WEBSOCKET_PORT']}"
        db.collection(u'new-instances').document(doc.document.id).set(new_doc)
    new_instance_callback.set()


def on_connection_req(collection_snapshot, changes, read_time):
    for doc in changes:
        print("got change")
        if doc.document.to_dict()['socket']:
            return
        new_doc = doc.document.to_dict()
        new_doc['socket'] = CLIENTS[0]['socket'].remote_address[0]
        db.collection(u'connection-req').document(doc.document.id).set(new_doc)
    connection_req_callback.set()


async def handle(websocket: websockets.WebSocketServerProtocol):
    print("Got connection")
    if websocket.remote_address[0] in [client['client_ip'] for client in AUTHORIZED_CLIENTS]:
        print("Client Authenticated")
    else:
        print("Client Auth failed, testing mode")
        # websocket.close()
        # return

    clientUUID = "router-" + str(uuid.uuid4())
    clientDict = {"uuid": clientUUID, "socket": websocket, "instance_name": ""}
    CLIENTS.append(clientDict)
    await websocket.send('{"action":"setId","data":"' + clientUUID + '"}')
    print("Client list:")
    for item in CLIENTS:
        print(item["uuid"])

    await websocket.wait_closed()
    print(f"Client {clientUUID} disconnected")
    CLIENTS.remove(clientDict)


async def serve():
    print("Serving websocket server")
    async with websockets.serve(handle, port=int(env['WEBSOCKET_PORT'])):
        await asyncio.Future()


if __name__ == "__main__":
    gcdlist = gcd.list_instances_in_group("management-node-deployer-1")
    if not gcdlist:
        pass
        # gcd.deploy_instance_group("management-node-deployer-1", "router-instance", env['INSTANCE_TEMPLATE'], 1)

    instance_watch = new_instances_ref.on_snapshot(on_new_instance_up)
    connection_watch = connection_req_ref.on_snapshot(on_connection_req)
    asyncio.run(serve())
