import threading
import uuid
from threading import Timer
import simplegcd.Deployer as gcd
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from os import environ as env
from Client import Client

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

join_req_ref = db.collection(u'meetings/management-node-deployer-1/clients').where(u'peer', u'==', "")
join_req_callback = threading.Event()

router = None
clients = []

def on_new_instance_up(collection_snapshot, changes, read_time):
    global router, clients
    for change in changes:
        if change.type.name != 'ADDED':
            return

        print(f'Received document snapshot: {change.document.id}')
        new_doc = change.document.to_dict()
        router = new_doc['instance_name']
        clients = []
        new_doc['registered'] = True
        db.collection(u'new-instances').document(change.document.id).set(new_doc)
    new_instance_callback.set()


def on_joining_client(collection_snapshot, changes, read_time):
    for change in changes:
        if change.type.name != 'ADDED':
            return
        new_doc = change.document.to_dict()
        new_doc['peer'] = router
        client_exists = False
        for client in clients:
            if client.id == new_doc["id"]:
                clients.remove(client)
                #router_command = {"command": "removeClient", "client_id": new_doc['id']}
                #db.collection(f'meetings/management-node-deployer-1/clients/{router}/commands') \
                    #.document().set(router_command)

        clients.append(Client(new_doc["id"], "management-node-deployer-1"))
        router_command = {"command": "registerClient", "client_id": new_doc['id']}
        db.collection(f'meetings/management-node-deployer-1/clients/{router}/commands')\
            .document().set(router_command)

        db.collection(u'meetings/management-node-deployer-1/clients').document(change.document.id).set(new_doc)
        route_all_clients()


    join_req_callback.set()


def route_all_clients():
    for client in clients:
        client.clear_routes(db, router)

    for src in range(0, len(clients)):
        dest_clients = []
        for dest in range(0, len(clients)):
            if dest == src: continue
            dest_clients.append(clients[dest].id)
        if len(dest_clients) == 0:
            continue
        else:
            clients[src].route(dest_clients, db, router)


def check_client_heartbeat():
    print("Checking heartbeat")
    disconnect = False
    for client in clients:
        if not client.heartbeat(db):
            print("Client Heartbeat not present for" + client.id)
            clients.remove(client)
        else:
            print("Client Heartbeat " + client.id)

    if disconnect:
        route_all_clients()

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

if __name__ == "__main__":
    # gcdlist = gcd.list_instances_in_group("management-node-deployer-1")
    # if not gcdlist:
    #     pass
        # gcd.deploy_instance_group("management-node-deployer-1", "router-instance", env['INSTANCE_TEMPLATE'], 1)

    instance_watch = new_instances_ref.on_snapshot(on_new_instance_up)
    join_watch = join_req_ref.on_snapshot(on_joining_client)
    print("Setup done")

    client_heartbeat = RepeatedTimer(2, check_client_heartbeat)
    client_heartbeat.start()

    input()

    client_heartbeat.stop()

