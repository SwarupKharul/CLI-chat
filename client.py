# Importing the relevant libraries
import websockets
import asyncio
import json


# The main function that will handle connection and communication
# with the server
async def listen():
    url = "ws://localhost:8000/ws"
    # Connect to the server
    async with websockets.connect(url, ping_interval=None) as ws:
        # Send a greeting message
        # await ws.send("Hello Server!")
        # Stay alive forever, listening to incoming msgs
        while True:
            my_message = input("Enter your message: ")
            my_msg = {"code": "message", "name": "vdkbv", "message": my_message}
            await ws.send(json.dumps(my_msg))
            msg = await ws.recv()
            # jsonify msg
            msg = json.loads(msg)
            # print the msg
            name = msg["name"]
            message = msg["message"]
            print("{}: {}".format(name, message), end="\r", flush=True)


# Start the connection
asyncio.get_event_loop().run_until_complete(listen())
# asyncio.run(listen())
