class Client:
    def __init__(self, id, roomId):
        self.id = id
        self.roomId = roomId
        self.routes = []
        pass

    def heartbeat(self, db):
        doc_ref = db.collection(f'meetings/management-node-deployer-1/clients/{self.id}/commands') \
            .document('heartbeat')

        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            doc_ref.set({"command": "heartbeat", "beat": False})
            return data["beat"]
        else:
            doc_ref.set({"command": "heartbeat", "beat": False})
            return True

    def route(self, dest_clients, db, router):
        router_command = {"command": "addRoute", "src_client": self.id, "dest_clients": dest_clients}
        db.collection(f'meetings/management-node-deployer-1/clients/{router}/commands') \
            .document().set(router_command)

    def clear_routes(self, db, router):
        router_command = {"command": "delAllRoutes", "client_id": self.id}
        db.collection(f'meetings/management-node-deployer-1/clients/{router}/commands') \
            .document().set(router_command)