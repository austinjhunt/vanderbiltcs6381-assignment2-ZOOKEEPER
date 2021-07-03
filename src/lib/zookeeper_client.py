""" All entities in pub/sub are clients of ZooKeeper, so they will each inherit from this class
for basic zookeeper client functionality
"""
import uuid
import sys
from kazoo.client import KazooClient, KazooState

class ZookeeperClient:
    def __init__(self, zookeeper_hosts=[]):
        self.zk_hosts = ','.join(zookeeper_hosts)
        # ZooKeeper client -> self.zk
        self.zk = None
        self.zk_instance_id = str(uuid.uuid4())
        # this is for write into the znode about the broker information
        self.znode_value = None
        # The ZNode all entities will be interested in watching
        self.zk_name = '/broker'

    def listener4state (self, state):
        if state == KazooState.LOST:
            self.debug ("Current state is now = LOST")
        elif state == KazooState.SUSPENDED:
            self.debug ("Current state is now = SUSPENDED")
        elif state == KazooState.CONNECTED:
            self.debug ("Current state is now = CONNECTED")
        else:
            self.debug ("Current state now = UNKNOWN !! Cannot happen")

    def connect_zk(self):
        try:
            self.debug(f"Try to connect with ZooKeeper server: hosts = {self.zk_hosts}")
            self.zk = KazooClient(self.zk_hosts)
            self.zk.add_listener (self.listener4state)
            self.debug(f"ZooKeeper Current Status = {self.zk.state}")
        except:
            self.debug("Issues with ZooKeeper, cannot connect with Server")

    def start_session(self):
        """ Start a Zookeeper Session """
        try:
            self.zk.start()
        except:
            self.debug(f"Exception thrown in start (): {sys.exc_info()[0]}")

    def stop_session (self):
        """ Stop a ZooKeeper Session """
        try:
            self.zk.stop()
        except:
            self.error(f"Exception thrown in stop (): {sys.exc_info()[0]}")
            return

    def close_connection(self):
        try:
            # now disconnect from the server
            self.zk.close()
        except:
            self.error(f"Exception thrown in close (): {sys.exc_info()[0]}")
            return

    def get_znode_value (self):
        """ ******************* retrieve a znode value  ************************ """
        try:
            self.debug (f"Checking if {self.zk_name} exists (it should)")
            if self.zk.exists (self.zk_name):
                self.debug (f"{self.zk_name} znode indeed exists; get value")
                # Now acquire the value and stats of that znode
                #value,stat = self.zk.get (self.zk_name, watch=self.watch)
                value, stat = self.zk.get (self.zk_name)
                # ip, pub_reg_port, sub_reg_port
                self.znode_value = value.decode("utf-8")
                self.debug(
                    f"Details of znode {self.zk_name}: value = {value}, "
                    f"stat = {stat}"
                    )
                self.debug(f"Values stored in field znode_value is {self.znode_value}")
            else:
                self.debug (f"{self.zk_name} znode does not exist, why?")
        except:
            self.error(f"Exception thrown checking for exists/get: {sys.exc_info()[0]}")
            return

    def create_znode (self):
        """ Create an ephemeral znode with name = self.zk_name and value =
        self.znode_value. Used by the broker specifically.  """
        try:
            self.debug(
                f"Creating an ephemeral znode {self.zk_name} with "
                f"value {self.znode_value }")
            self.zk.create(self.zk_name, value=self.znode_value.encode('utf-8'),
                ephemeral=False)
            self.debug(f"Ephemeral znode <{self.zk_name},{self.znode_value}> created!")

        except:
            self.debug("Exception thrown in create (): ", sys.exc_info()[0])
            return

    def modify_znode_value(self, new_val):
        """ Modify a znode value
        Args:
        new_val (str): new value to set on the /broker znode """
        try:
            # Now let us change the data value on the znode and see if
            # our watch gets invoked
            self.debug(f"Setting a new value = {new_val} on znode {self.zk_name}")
            if self.zk.exists (self.zk_name):
                self.debug(f"{self.zk_name} znode still exists :-)")
                self.debug("Setting a new value on znode")
                self.zk.set(self.zk_name, new_val)
                # Now see if the value was changed
                value,stat = self.zk.get(self.zk_name)
                self.debug(
                    f"New value at znode {self.zk_name}: "
                    f"value = {value}, stat = {stat}"
                    )
            else:
                self.debug(f"{self.zk_name} znode does not exist")
        except:
            self.debug("Exception thrown checking for exists/set: ", sys.exc_info()[0])
            return