# Paxos Blockchain Project

### Project Overview
#### Block Contents
- Each block in the blockchain holds transactions
- Hash of previous block + nonce where hash ends with 0-4
#### Client Behavior
- Money Transfer (sender, receiver, amount)
- Fail Link: Simulate Link Failure
- Fix Link: Bring Link back Online
- Fail Process: Process persists through failure
- Print Blockchain, Balance, Queue
#### Communication
- Use paxos for block communication

##### Paxos Communication
- Proposer: Send prepare with sequence #
- Acceptor: Promise to not receive lower values
- Prop-Accept: Value to propose
- Accept: Tell leader value has been accepted
- Decision: Leader distributes value