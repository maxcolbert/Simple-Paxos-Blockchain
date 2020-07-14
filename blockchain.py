import pickle

# Single Transaction
class Transaction:
    def __init__(self, sender, receiver, amt):
        self.sender = sender
        self.receiver = receiver
        self.amt = amt

    def __eq__(self, other):
        if self.sender == other.sender:
            if self.receiver == other.receiver:
                if self.amt == other.amt:
                    return True
        return False
    def __str__(self):
        return f'[{self.sender}, {self.receiver}, {self.amt}]'

# Block of Transactions
class Block:
    def __init__(self, transactions, phash, nonce):
        """
        transactions: list of transactions
        phash: hash of previous block + nonce
        nonce: value used to generate hash
        """
        self.transactions = transactions
        self.phash = phash
        self.nonce = nonce
        self.ahead = None
    # Persistence & Serialization
    def __getstate__(self):
        return self.__dict__
    def __setstate__(self, vals):
        self.__dict__ = vals
    def __str__(self):
        msg = f'Block ID: {id(self)}\n'
        tstring = [str(t) for t in self.transactions]
        msg += f'Transactions: {tstring}\n'
        msg += f'Hash: {self.phash}\n'
        msg += f'Nonce: {self.nonce}\n'
        return msg
        
# List Based Transaction Storage
class Blockchain:
    def __init__(self):
        self.chain = []
        self.head = None
        self.tail = None
        self.depth = 0

    # Append block to transaction list
    def append(self, block):
        if not self.head:
            self.head = block
            self.tail = block
        else:
            self.tail.ahead = block
            self.tail = block
        self.chain.append(block)
        self.depth += 1

    # User Request Chain Printing
    def print_chain(self):
        msg = '\n'
        for item in self.chain:
            msg += str(item)
        print(msg)
        return None
        
    # User Requested Chain Depth
    def get_depth(self):
        return self.depth
