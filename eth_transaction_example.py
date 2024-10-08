#!/usr/bin/python3

import zymkey
import binascii
import hashlib
import rlp
from Crypto.Hash import keccak
from rlp import encode
from rlp.sedes import Binary, big_endian_int, binary
from eth_account._utils.legacy_transactions import serializable_unsigned_transaction_from_dict, encode_transaction
from web3 import Web3

class Transaction(rlp.Serializable):
    fields = [
        ("nonce", big_endian_int),
        ("gas_price", big_endian_int),
        ("gas", big_endian_int),
        ("to", Binary.fixed_length(20, allow_empty=True)),
        ("value", big_endian_int),
        ("data", binary),
        ("v", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    ]

#Utility function for checking the from/to/(v,r,s) values of a raw transaction
def decode_raw_tx(raw_tx):
    tx = rlp.decode(raw_tx, Transaction)
    from_addr = w3.eth.account.recover_transaction(raw_tx)
    to_addr = w3.toChecksumAddress(tx.to) if tx.to else None
    r = hex(tx.r)
    s = hex(tx.s)
    chain_id = (tx.v - 35) // 2 if tx.v % 2 else (tx.v - 36) // 2
    print("\nDecoded raw transaction check:\nfrom:\n%s\nto:\n%s\nr:\n%s\ns:\n%s\nv:\n%s" % (from_addr, to_addr, r, s, tx.v))
    return tx

#create web3 instance, from infura project (node) connecting to ropsten test network
w3 = Web3(Web3.HTTPProvider('https://ropsten.infura.io/v3/bac2734b0e144a6dbb46c0e118ce1ef7'))

#Example receiver's address
addr = '0x15C25E6EB5dE729d7e310d059e59659cCB86E6f6'

#MAKE SURE TO GENERATE A "secp256k1" KEY PAIR ON THE HSM6, this example uses slot 16
#Get ECDSA secp256k1 public key from zymkey and generate our Ethereum sender's checksum address
zymkey_pub_key_slot = 16
pub_key = zymkey.client.get_public_key(zymkey_pub_key_slot)
print("zymkey secp256k1 public key:\n%s" % pub_key)

keccak_hash = keccak.new(digest_bits=256)
keccak_hash.update(pub_key)
keccak_digest = keccak_hash.hexdigest()
# Take the last 20 bytes
wallet_len = 40
wallet_addr = "0x" + keccak_digest[-wallet_len:]

checksum = Web3.toChecksumAddress(wallet_addr)

# How eip-55 calculates checksum
# checksum = "0x"
# # Remove ‘0x’ from the address
# address = wallet_addr[2:]
# address_byte_array = address.encode("utf-8")
# keccak_hash = keccak.new(digest_bits=256)
# keccak_hash.update(address_byte_array)
# keccak_digest = keccak_hash.hexdigest()
# for i in range(len(address)):
#     address_char = address[i]
#     keccak_char = keccak_digest[i]
#     if int(keccak_char, 16) >= 8:
#         checksum += address_char.upper()
#     else:
#         checksum += str(address_char)

print("Eth Checksum:\n%s" % checksum)

print("Valid checksum:\n%s" % Web3.isAddress(checksum))


#estimate gas
gas = w3.eth.estimate_gas({'to': addr, 'value': 1})
print("Gas value:\n %i" % gas)

#grab nonce value of sender's account. nonce = number of transactions
nonce = w3.eth.getTransactionCount(checksum)
print("Nonce value:\n %i" % nonce)

#Ropsten chain ID is 3
chain_id = 3

# prepare the transaction, chainID 3 is ropsten
transaction = {
    'to': addr,
    'gas': gas,
    'gasPrice': 5000000,
    'nonce': nonce,
    'value': 1,
    'data': '0x',
    'chainId': chain_id
}

#----------------------------------------Send Transaction with zymkey signature-----------------------------------------------------------------
#Sign a transaction with a signature generated by hsm6

#Serialize the transaction
#Note: Transactions are serialized in this data structure order: Nonce, Gas price, Gas limit, To address, Value, Data, V, R ,S
serializable_transaction = serializable_unsigned_transaction_from_dict(transaction)
print("serializable_transaction:\n%s" % serializable_transaction)

#RLP encode the transaction
encoded_transaction = encode(serializable_transaction)
print("encoded transaction:\n%s" %  binascii.hexlify(encoded_transaction).decode("utf-8"))

#Per Ethereum standards, Keccak hash rlp encoded transaction
keccak_hash=keccak.new(digest_bits=256)
keccak_hash.update(encoded_transaction)
print("keccak_hash:\n%s" % keccak_hash.hexdigest())

N = 115792089237316195423570985008687907852837564279074904382605163141518161494337
# sign the transaction hash and calculate v, r, s values
signature, rec_id = zymkey.client.sign_digest(keccak_hash, zymkey_pub_key_slot, return_recid=True)
print ("ECDSA Signature:\n%s" % signature)

print("ECDSA Sig Length:\n%s" % len(signature))

print("ECDSA Sig Recovery_id:\n%s" % rec_id.value)

#Signature consists of a R, S, V
#R is the first half of the signature converted to int
#S is the second half of the signature converted to int
#From EIP 155, V = chainId * 2 + 35 + recovery_id of public key
print ("R(hex):\n%s" % binascii.hexlify(signature[:32]))
print ("S(hex):\n%s" % binascii.hexlify(signature[-32:]))

r = int.from_bytes(signature[:32], "big")
s = int.from_bytes(signature[-32:], "big")

y = rec_id.value
if((s*2) >= N):
   y ^= 1
   s = N - s

v = chain_id * 2 + 35 + y

print ("R:\n%s" % r)
print ("S:\n%s" % s)
print ("V:\n%s" % v)

#Verify the ECDSA signature.
verify_sig = zymkey.client.verify_digest(keccak_hash, signature, True, zymkey_pub_key_slot, False)
print("Verify sig:\n%s" % verify_sig)

# RLP encode the transaction along with the full signature
encoded_transaction = encode_transaction(serializable_transaction, vrs=(v, r, s))
print("encoded transaction:\n%s" % binascii.hexlify(encoded_transaction).decode("utf-8"))

decoded_transaction = decode_raw_tx(encoded_transaction)
print("decoded_transaction:\n%s" % decoded_transaction)


#send raw transaction
transaction_result_hash = w3.eth.sendRawTransaction(encoded_transaction)
print("Transaction broadcast hash:\n%s" % binascii.hexlify(transaction_result_hash).decode("utf-8"))
#-------------------------------------------------------------------------------------------------------------------------------------------------
