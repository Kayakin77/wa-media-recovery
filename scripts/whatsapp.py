#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import base64
import json
import io
import hashlib
import hmac
import traceback
import binascii
from threading import Thread, Timer
from datetime import datetime

import websocket
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import pyqrcode

# Importes locales (asegúrate de que estos archivos existan en la carpeta)
from utilities import getTimestamp, eprint
from whatsapp_binary_reader import whatsappReadBinary

def HmacSha256(key, sign):
    return hmac.new(key, sign, hashlib.sha256).digest()

def HKDF(key, length, appInfo=""):
    # Implementación compatible con Python 3
    info = appInfo.encode() if isinstance(appInfo, str) else appInfo
    key = hmac.new(b"\0"*32, key, hashlib.sha256).digest()
    keyStream = b""
    keyBlock = b""
    blockIndex = 1
    while len(keyStream) < length:
        keyBlock = hmac.new(key, msg=keyBlock + info + bytes([blockIndex]), digestmod=hashlib.sha256).digest()
        blockIndex += 1
        keyStream += keyBlock
    return keyStream[:length]

def AESDecrypt(key, ciphertext):
    iv = ciphertext[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = cipher.decrypt(ciphertext[16:])
    # Intentar quitar padding PKCS7, si falla devolver bruto
    try:
        return unpad(plaintext, AES.block_size)
    except:
        return plaintext

class WhatsAppWebClient:
    def __init__(self, onOpenCallback, onMessageCallback, onCloseCallback):
        self.websocketIsOpened = False
        self.onOpenCallback = onOpenCallback
        self.onMessageCallback = onMessageCallback
        self.onCloseCallback = onCloseCallback
        self.activeWs = None
        self.messageSentCount = 0
        self.messageQueue = {}
        
        self.loginInfo = {
            "clientId": None,
            "serverRef": None,
            "privateKey": None,
            "publicKey": None,
            "key": {"encKey": None, "macKey": None}
        }
        self.connInfo = {
            "clientToken": None, "serverToken": None, "browserToken": None,
            "secret": None, "sharedSecret": None, "me": None
        }
        self.connect()

    def onOpen(self, ws):
        self.websocketIsOpened = True
        if self.onOpenCallback and "func" in self.onOpenCallback:
            self.onOpenCallback["func"](self.onOpenCallback)
        print("WhatsApp backend Websocket opened.")

    def onMessage(self, ws, message):
        try:
            # En Python 3, los mensajes de websocket pueden venir como bytes o str
            if isinstance(message, bytes):
                message = message.decode('utf-8', errors='ignore')

            messageSplit = message.split(",", 1)
            messageTag = messageSplit[0]
            messageContent = messageSplit[1] if len(messageSplit) > 1 else ""

            if messageTag in self.messageQueue:
                pend = self.messageQueue[messageTag]
                if pend["desc"] == "_login":
                    res = json.loads(messageContent)
                    self.loginInfo["serverRef"] = res["ref"]
                    
                    # --- REEMPLAZO DE CURVE25519 ---
                    self.loginInfo["privateKey"] = x25519.X25519PrivateKey.generate()
                    pub_key = self.loginInfo["privateKey"].public_key()
                    pub_bytes = pub_key.public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw
                    )
                    
                    qrCodeContents = f"{self.loginInfo['serverRef']},{base64.b64encode(pub_bytes).decode()},{self.loginInfo['clientId']}"
                    
                    svgBuffer = io.BytesIO()
                    pyqrcode.create(qrCodeContents, error='L').svg(svgBuffer, scale=6, background="rgba(0,0,0,0.0)", module_color="#122E31", quiet_zone=0)
                    
                    if "callback" in pend and pend["callback"]:
                        qr_data = {
                            "type": "generated_qr_code",
                            "image": "data:image/svg+xml;base64," + base64.b64encode(svgBuffer.getvalue()).decode(),
                            "content": qrCodeContents
                        }
                        pend["callback"]["func"](qr_data, pend["callback"])
            
            else:
                # Manejo de mensajes JSON o Binarios cifrados
                try:
                    jsonObj = json.loads(messageContent)
                    self.handleJson(jsonObj)
                except ValueError:
                    if self.loginInfo["key"]["encKey"]:
                        # Lógica de descifrado para mensajes binarios (omitiendo por brevedad, requiere keys)
                        pass

        except Exception:
            eprint(traceback.format_exc())

    def handleJson(self, jsonObj):
        if isinstance(jsonObj, list) and len(jsonObj) > 0:
            if jsonObj[0] == "Conn":
                self.connInfo.update(jsonObj[1])
                # Aquí se realizaría el intercambio de llaves final (Diffie-Hellman)
                print(f"Conectado como: {jsonObj[1].get('pushname')}")

    def connect(self):
        self.activeWs = websocket.WebSocketApp(
            "wss://web.whatsapp.com/ws",
            on_message=self.onMessage,
            on_open=self.onOpen,
            header={"Origin: https://web.whatsapp.com"}
        )
        self.websocketThread = Thread(target=self.activeWs.run_forever)
        self.websocketThread.daemon = True
        self.websocketThread.start()

    def generateQRCode(self, callback=None):
        self.loginInfo["clientId"] = base64.b64encode(os.urandom(16)).decode()
        messageTag = str(getTimestamp())
        self.messageQueue[messageTag] = {"desc": "_login", "callback": callback}
        message = f'{messageTag},["admin","init",[0,4,2026],["Termux","Chrome"]," {self.loginInfo["clientId"]}",true]'
        self.activeWs.send(message)

    def disconnect(self):
        if self.activeWs:
            self.activeWs.send('goodbye,,["admin","Conn","disconnect"]')
