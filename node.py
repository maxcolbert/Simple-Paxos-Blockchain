import hashlib
import threading
import ipaddress
import sys
import time
import random
import math
import struct
from socket import *

from options import options
from blockchain import *

# run via python3 node.py <client_id>
inp_clientID = 1
try:
    inp_clientID = int(sys.argv[1:][0])
except:
    inp_clientID = 1


class Client():
    def __init__(self, num):
        self.num = num
        self.seq_num = num
        # pickle seralization of current block
        self.proposal = None
        self.clock = [0]
        self.leader = 0
        self.balance = 100
        self.outgoing = 0
        self.chain = Blockchain()
        self.queue = []
        self.promises = 1
        self.promised = False
        self.accepts = 1
        self.others = [x for x in range(1, options['NUM_PROCS']+1) if x != num]
        # socket
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.bind((options['ip'], options[inp_clientID]))
        self.sock.listen(5)
        
    def print_balance(self):
        print(f'Process {self.num} Balance: ${self.balance}')

    def print_queue(self):
        qstring = [str(t) for t in self.queue]
        print(f'Process {self.num} Queue:\n {qstring}')
        
    def print_chain(self):
        self.chain.print_chain()

    def add_transaction(self, sendr, recvr, amt):
        tmp = Transaction(sendr, recvr, amt)
        if (tmp.sender == self.num):
            self.outgoing += tmp.amt
            self.broadcast(f'[Transaction, {sendr}, {recvr}, {int(amt)}]')
        self.queue.append(tmp)
        if (len(self.queue) == 1):
            self.start_timer()

    # start timer countdown to become leader and propose block
    # call this function in 3 scenarios:
    # 1: this process loses leader election and must retry later
    # 2: this process proposes a previously accepted value and must now retry
    # 3: this process just added a transaction to its empty queue
    def start_timer(self):
        countdown = random.randint(3, 5)
        while not countdown == 0:
            time.sleep(1)
            countdown -= 1
        success = False
        while not success and len(self.queue) > 0:
            self.seq_num += random.randint(1, options['NUM_PROCS']) 
            success = self.propose_block()

    def fail_node(self, fname):
        pickle.dump(self.others, open(fname+'others', 'wb'))
        pickle.dump(self.balance, open(fname+'balance', 'wb'))

    def revive_node(self, fname):
        self.balance = pickle.load(open(fname+'balance', 'rb'))
        self.others = pickle.load(open(fname+'others', 'rb'))
        self.get_current_chain(self.others[0])
            
    def fail_link(self, recvr):
        # kill process here
        if int(recvr) in self.others:
            self.others.remove(int(recvr))

    def send_link_fail(self, recvr):
        msg = f'[FAIL_LINK, {self.num}]'
        sender = socket(AF_INET, SOCK_STREAM)
        sender.connect((options['ip'], options[recvr]))
        sender.sendall(msg.encode())
        sender.close()

    def send_link_fix(self, recvr):
        msg = f'[FIX_LINK, {self.num}]'
        sender = socket(AF_INET, SOCK_STREAM)
        sender.connect((options['ip'], options[recvr]))
        sender.sendall(msg.encode())
        sender.close()

    def fix_link(self, recvr):
        # request from first available node
        if int(recvr) not in self.others:
            self.others.append(int(recvr))
            self.others.sort()

    def compare_blockchains(self, recv):
        recv_chain = pickle.loads(recv)
        if (self.chain.get_depth() < recv_chain.get_depth()):
            self.chain = recv_chain

    def get_current_chain(self, nodeNum):
        print(f'Checking node {nodeNum} on port {options[nodeNum]} for current blockchain')
        # msg format: [RQST_CHAIN]
        chain_byte_array = ','.join(str(i) for i in pickle.dumps(self.chain))
        rqstMsg = f'[RQST_CHAIN, {chain_byte_array}]'
        sender = socket(AF_INET, SOCK_STREAM)
        sender.connect((options['ip'], options[nodeNum]))
        sender.sendall(rqstMsg.encode())
        response = sender.recv(4096).decode()
        converted_response = bytes(eval('['+response+']'))
        self.compare_blockchains(converted_response)
        sender.close()

    def broadcast(self, msg):
        for i in self.others:
            # broadcast to all that are not broken
            sender = socket(AF_INET, SOCK_STREAM)
            sender.connect((options['ip'], options[i]))
            sender.sendall(msg.encode())
            sender.close()

    def send(self, msg, recvr):
        if recvr in self.others:
            # only if recvr link is not broken
            sender = socket(AF_INET,SOCK_STREAM)
            sender.connect((options['ip'], options[recvr]))
            sender.sendall(msg.encode())
            sender.close()

    def verify_block(self, pickled_block):
        # evaluate parameter pickled_block as an array and then convert the array to bytes
        bytes_pickled_block = bytes(eval('['+pickled_block+']'))
        tmp = pickle.loads(bytes_pickled_block)
        # verify transactions
        verification = str(pickle.dumps(self.chain.tail)) + str(tmp.nonce)
        check = hashlib.sha256(verification.encode()).hexdigest()
        if ('0' <= check[-1] <= '4' and check == tmp.phash) or not self.chain.tail:
            return True
        return False            

    def append_block(self, pickled_block):
        tmp = pickle.loads(pickled_block)
        self.chain.append(tmp)
        # adjust balance per each transaction
        for transaction in tmp.transactions:
            # transaction format: [sendr, recvr, amt]
            if int(transaction.receiver) == self.num:
                # if its recvr, add
                self.balance += int(transaction.amt)
            if int(transaction.sender) == self.num:
                # if its sendr, subtract
                self.balance -= int(transaction.amt)
        # remove transactions processed already
        # assumes tmp.transactions is subset of self.queue
        # this is verified in verify_block
        for transaction in tmp.transactions:
            if transaction.sender == self.num:
                self.outgoing -= transaction.amt
            if transaction in self.queue:
                self.queue.remove(transaction)

    def calculate_nonce(self, block):
        nonce = 0
        block_string = pickle.dumps(block)
        while True:
            hash_string = str(block_string) + str(nonce)
            hash_val = hashlib.sha256(hash_string.encode()).hexdigest()
            if '0' <= hash_val[-1] <= '4':
                return nonce, hash_val
            nonce += 1
        
    def propose_block(self):
        self.proposal = None
        prep = f'[Prepare, {self.seq_num}, {self.num}, {self.chain.get_depth()}]'
        self.broadcast(prep)
        counter = 0
        majority = math.floor(options['NUM_PROCS']/2)+1
        while (self.promises <= majority and counter < 5):
            time.sleep(1)
            counter += 1
        # calling thread should retry with updated seq_num
        if (self.promises <= majority):
            return False
        # check for piggybacked value on promise
        if not self.proposal:
            prev = self.chain.tail
            if not prev:
                prev = Block(0, 0, 0)
            nonce, prev_hash = self.calculate_nonce(prev)
            self.proposal = Block(self.queue, prev_hash, nonce)
            self.proposal = pickle.dumps(self.proposal)
        # send request for value
        # convert self.proposal to an array of bytes
        # stringified and separated by commas
        array_of_bytes = ','.join(str(i) for i in self.proposal)
        req = f'[Request, {self.seq_num}, {self.num}, {self.chain.get_depth()}, {array_of_bytes}]'
        self.broadcast(req)
        # wait for accept values
        counter = 0
        while (self.accepts <= majority and counter < 5):
            time.sleep(1)
            counter += 1
        # calling thread should retry with updated seq_num
        if (self.accepts <= majority):
            return False
        dec = f'[Decision, {self.seq_num}, {self.num}, {self.chain.get_depth()}, {array_of_bytes}]'
        self.broadcast(dec)
        self.append_block(self.proposal)
        return True

    # Communication Thread
    def receive(self):
        promise = (0, 0)
        value = None
        while True:
            try:
                stream, addr = self.sock.accept()
                message = stream.recv(4096).decode()
                msg = message[1:-1].split(', ')
                # print("MSG RECV: ", message)
                # transaction recorded in queue, not processed until added as block
                if msg[0] == 'Transaction':
                    # msg format: [transaction, sender, receiver, amount]
                    self.queue.append(Transaction(int(msg[1]), int(msg[2]), int(msg[3])))
                    # self.add_transaction(int(msg[1]), int(msg[2]), int(msg[3]))
                elif msg[0] == 'Prepare':
                    # msg format: [prepare, seq_num, pid, depth]
                    # Only accept messages which have equal or greater chain
                    if self.chain.get_depth() > int(msg[3]):
                        continue
                    elif self.chain.get_depth() < int(msg[3]):
                        self.get_current_chain(int(msg[2]))
                    ballot_num = (int(msg[1]), int(msg[2]))
                    promise = max(promise, ballot_num)
                    # make promise to presumptive leader
                    if promise == ballot_num:
                        # [promise, seq_num, proposer_pid, pickled value]
                        responseMsg = f'[Promise, {msg[1]}, {msg[2]}'
                        # piggyback previously accepted value (pickled block)
                        if value:
                            responseMsg += f', {value}]'
                        else:
                            responseMsg += ']'
                        self.send(responseMsg, int(msg[2]))
                        self.promised = True
                        # self.leader = int(msg[2])
                elif msg[0] == 'Promise':
                    # msg format: [promise, seq_num, proposer_pid, pickled block]
                    ballot_num = (int(msg[1]), int(msg[2]))
                    promise = max(promise, ballot_num)
                    if len(msg) == 4:
                        # use piggybacked value if provided
                        self.proposal = msg[3]
                    self.promises += 1
                elif msg[0] == 'Request':
                    # msg format: [request, seq_num, pid, depth, pickled block]
                    if self.chain.get_depth() > int(msg[3]):
                        continue
                    ballot_num = (int(msg[1]), int(msg[2]))
                    if not promise == ballot_num:
                        continue
                    if value and not msg[4] == value:
                        continue
                    if self.verify_block(msg[4]):
                        value = msg[4]
                        promise = max(promise, ballot_num)
                        responseMsg = f'[Accept, {msg[1]}, {msg[2]}, {msg[3]}, {msg[4]}]'
                        self.send(responseMsg, int(msg[2]))
                elif msg[0] == 'Accept':
                    # msg format: [accept, seq_num, pid, depth, pickled block]
                    if self.chain.get_depth() > int(msg[3]):
                        continue
                    ballot_num = (int(msg[1]), int(msg[2]))
                    if not promise == ballot_num:
                        continue
                    if bytes(eval('['+msg[4]+']')) == self.proposal:
                        self.accepts += 1
                elif msg[0] == 'Decision':
                    # msg format: [decision, seq_num, pid, depth, pickled block]
                    if self.chain.get_depth() > int(msg[3]):
                        continue
                    ballot_num = (int(msg[1]), int(msg[2]))
                    if not promise == ballot_num:
                        continue
                    if msg[4] == value:
                        self.append_block(bytes(eval('['+msg[4]+']')))
                    # reset for next round
                    promise = (0, 0)
                    value = None
                    # Start new election after this round
                    roundthread = threading.Thread(target=self.start_timer)
                    roundthread.daemon = True
                    roundthread.start()
                elif msg[0] == 'RQST_CHAIN':
                    # request chain from another process
                    recv_chain = bytes(eval('['+msg[1]+']'))
                    self.compare_blockchains(recv_chain)
                    chain_byte_array = ','.join(str(i) for i in pickle.dumps(self.chain))
                    stream.send(chain_byte_array.encode())
                elif msg[0] == 'FAIL_LINK':     # sender = msg[1]
                    self.fail_link(msg[1])
                elif msg[0] == 'FIX_LINK':     # sender = msg[1]
                    self.fix_link(msg[1])
                    self.get_current_chain(int(msg[1]))
                stream.close()
            except timeout:
                stream.close()
            except error:
                stream.close()

# SET UP client:
client = Client(inp_clientID)

pro1 = threading.Thread(target=client.receive)
pro1.daemon = True
pro1.start()

while True:
    print('\nInput 1 to send, 2 to print chain, 3 to print balance, 4 to print the queue, 5 to fail a connection, 6 to fix a connection, 7 to fail this node, 8 to request a chain, 9 to print the working links, or 10 to revive this node:')
    inp = int(input())
    if (inp == 1):
        print('Select Receiver ID (1, 2, 3, 4, 5):')
        receiverID = int(input())
        print('State send amount:')
        amt = int(input())
        if (amt > (client.balance - client.outgoing)):
            print('Failure: Insufficient Funds')
        else:
            transactThread = threading.Thread(target=client.add_transaction, args=(client.num, receiverID, amt, ))
            transactThread.daemon = True
            transactThread.start()
    elif (inp == 2):
        client.print_chain()
    elif (inp == 3):
        client.print_balance()
    elif (inp == 4):
        client.print_queue()
    elif (inp == 5):
        print(f'Input Receiver ID to FAIL {client.others}:')
        receiverID = int(input())
        client.fail_link(receiverID)
        client.send_link_fail(receiverID)
    elif (inp == 6):
        other_links = set([1, 2, 3, 4, 5]) - set([client.num])
        fixable_links = [item for item in (other_links) if item not in client.others]
        if (len(fixable_links)>0):
            print(f'Input Receiver ID to FIX {fixable_links}:')
            receiverID = int(input())
            client.fix_link(receiverID)
            client.send_link_fix(receiverID)
        else:
            print('None to fix')
    elif (inp == 7):
        client.fail_node(input('Filename to save data: '))
        sys.exit()
    elif (inp == 8):
        print(f'Input Receiver ID to request chain from:')
        receiverID = int(input())
        client.get_current_chain(nodeNum)
    elif (inp == 9):
        print('Working links: ', client.others)
    elif (inp == 10):
        fname = input('Filename for recovery: ')
        client.revive_node(fname)
    else:
        print('Invalid...')
