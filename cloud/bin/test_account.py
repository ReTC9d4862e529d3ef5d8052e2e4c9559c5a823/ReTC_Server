#!/usr/local/bin/python3.6
import json
import sys
import os
import asyncio
import base64
import aiohttp
from enum import Enum, Flag, auto

from aiohttp import ClientSession


class Rule(Flag):
    EXCHANGE_ONCE = auto()
    EXCHANGE_LIMITED_TO_ACCOUNTS = auto()
    EXCHANGE_ONCE_PER_ACCOUNT = auto()

    def describe(self, check=None):
        print(bool(self & check))
        return self.name, self.value

    def __str__(self):
        return '{0}'.format(self.value)

    def getExchangeOnce(self):
        if self & self.EXCHANGE_ONCE:
            print(bool(self & self.EXCHANGE_ONCE))
            return {"type": "EXCHANGE_ONCE"}
        else:
            return None

    def getExchangeOncePerAccount(self):
        if self & self.EXCHANGE_ONCE_PER_ACCOUNT:
            print(bool(self & self.EXCHANGE_ONCE_PER_ACCOUNT))
            return {"type": "EXCHANGE_ONCE_PER_ACCOUNT"}
        else:
            return None

    def getExchangeLimitedToAccount(self, toPublicKey):
        if self & self.EXCHANGE_LIMITED_TO_ACCOUNTS:
            print(bool(self & self.EXCHANGE_LIMITED_TO_ACCOUNTS))
            return {
                "type": "EXCHANGE_LIMITED_TO_ACCOUNTS",
                "value": [
                    [toPublicKey]
                ]
            }
        else:
            return None

    def getRules(self, vals, toPublicKey=None):
        val = self.getExchangeOnce()
        if val is not None:
            vals.append(val)

        val = self.getExchangeOncePerAccount()
        if val is not None:
            vals.append(val)

        val = self.getExchangeLimitedToAccount('KEY')
        if not None in (val, toPublicKey):
            vals.append(val)

        return vals


rules = Rule.EXCHANGE_ONCE | Rule.EXCHANGE_LIMITED_TO_ACCOUNTS
vals = []


def error():
    try:
        # assert(0)
        raise AssertionError
    except AssertionError as e:
        # raise e
        print('ERR')
        raise


# try:
#     error()
# except Exception as e:
#     raise e

# raise AssertionError('test')
# raise ValueError('test')
# print(rules.getRules(vals, 'KEY'))

# sys.exit(1)
adminAccount = {'email': 'admin@retc.io', 'password': 'b21izJw23qA'}
accounts = [
    adminAccount,
    {'email': 'testuserA@retc.io', 'password': 'TestW5XOfMoJy30'},
    {'email': 'testuserB@retc.io', 'password': 'TestW5XOfMoJy30'}
]
getAdminAccount = (lambda: accounts[0])
# sys.exit(1)

TOKENS = {}
URL = 'http://127.0.0.1:8041/api'


def get_accept_offer_payload(offer_id, count, target):
    return ('offers/%s/accept' % offer_id, 'patch', {"count": count, "target": target})


def getOfferPayload(label, description, source, target, sourceQuantity, targetQuantity, publicKey):
    offerPayload = {
        "description": description,
        "label": label,
        "rules": [
            {
                "type": "EXCHANGE_LIMITED_TO_ACCOUNTS",
                "value": [
                    [publicKey]
                ]
            }
        ],
        "source": source,
        "sourceQuantity": sourceQuantity,
        "target": target,
        "targetQuantity": targetQuantity
    }
    return ('offers', offerPayload)


print(getOfferPayload('label', 'description', 'source', 'target',
                      'sourceQuantity', 'targetQuantity', 'publicKey'))


async def send_api(url, method, data, token=None):
    headers = None if token is None else {'Authorization': token}
    async with aiohttp.ClientSession(headers=headers) as session:
        # async with _method(URL+'/'+url,json=data) as resp:
        async with getattr(session, method)(URL + '/' + url, json=data) as resp:
            result = json.loads(await resp.text())
            try:
                assert resp.status == 200
            except AssertionError as e:
                raise AssertionError(await resp.text()) from e
            return result


async def get_auth(data):
    async with aiohttp.ClientSession() as session:
        async with session.post(URL + '/authorization', json=data) as resp:
            assert resp.status == 200
            # print(await resp.text())
            result = json.loads(await resp.text())
            return result


async def get_account_info(uid, token):
    headers = {'Authorization': token}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(URL + '/accounts/' + uid) as resp:
            assert resp.status == 200
            # print(await resp.text( ))
            return json.loads(await resp.text())


async def get_account_offers(token):
    headers = {'Authorization': token}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(URL + '/accounts/offers') as resp:
            assert resp.status == 200
            # print(await resp.text( ))
            return json.loads(await resp.text())


def get_account_holding(asset, account):
    for holding in account['holdings']:
        if holding['asset'] == asset:
            return holding


def get_account_offer(label, account):
    for offer in account['offers']:
        if offer['label'] == label:
            return offer


async def getInitialProvision():
    admin_account = getAdminAccount()
    offer_id = get_account_offer('RTC Provision', admin_account)['id']
    for accountIdx in range(1, 3):
        userAccount = accounts[accountIdx]
        (api, method, payload) = get_accept_offer_payload(offer_id, 1, get_account_holding('RTC', userAccount)['id'])
        try:
            await send_api(api, method, payload, userAccount['token'])
        except AssertionError as e:
            print(e)
            raise
            pass


def getUserInfo(_token):
    _user = _token.split('.')[1]
    _user += "=" * ((4 - len(_user) % 4) % 4)
    user = base64.b64decode(_user)
    return json.loads(user)


async def refresh_accounts():
    global accounts

    for idx, account in enumerate(accounts):
        _token = account['token']
        userObj = getUserInfo(_token)

        _account = await get_account_info(userObj['public_key'], _token)
        accounts[idx] = {**accounts[idx], **_account}

        _offers = await get_account_offers(_token)
        accounts[idx] = {**accounts[idx], 'offers': _offers}


async def start():
    global accounts

    for idx, account in enumerate(accounts):
        # _token = (await getAuth(val))['authorization']
        _token = (await send_api('authorization', 'post', account))['authorization']
        account['token'] = _token
        # userObj = getUserInfo(_token)
        #
        # _account = await get_account_info(userObj['public_key'], _token)
        # accounts[idx] = {**accounts[idx], **_account}
        #
        # _offers = await get_account_offers(_token)
        # accounts[idx] = {**accounts[idx], 'offers': _offers}

    await refresh_accounts()
    # await getInitialProvision()
    print(json.dumps(accounts, indent=4, sort_keys=True))


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start())


main()
sys.exit(1)

authToken = {}

user = accounts[1]
print(type(accounts[0].get('email')))
print(type(user))
print(user['email'])
authToken[user['email']] = user
print(json.dumps(authToken, indent=4, sort_keys=True))
sys.exit(1)


async def msg(text):
    await asyncio.sleep(0.1)
    print(text)


async def long_operation():
    print('long_operation started')
    await asyncio.sleep(3)
    print('long_operation finished')


async def main():
    await msg('first')

    # Now you want to start long_operation, but you don't want to wait it finised:
    # long_operation should be started, but second msg should be printed immediately.
    # Create task to do so:
    task = asyncio.ensure_future(long_operation())
    # await long_operation()
    await msg('second')

    # Now, when you want, you can await task finised:
    # await task


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

# line = 'This,is,a,sample,string'
# result = bool('sample' in line)
# print(result)
# myPath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# print(myPath)

# def test():
#   print(__name__)

# test()

# holdings = [
#   {
#     'label': 'RTC Source',
#     'description': 'Supply RTC asset',
#     'asset': 'RTC',
#     'quantity': '9007199254740991',
#   }, {
#     'label': 'RTR Source',
#     'description': 'Supply RTR asset',
#     'asset': 'RTR',
#     'quantity': '9007199254740991',
#   }, {
#     'label': 'REU Source',
#     'description': 'Supply REU asset',
#     'asset': 'REU',
#     'quantity': '9007199254740991',
#   }, {
#     'label': 'RER Source',
#     'description': 'Supply RER asset',
#     'asset': 'RER',
#     'quantity': '9007199254740991',
#   }, {
#     'label': 'RRE Source',
#     'description': 'Supply RRE asset',
#     'asset': 'RRE',
#     'quantity': '9007199254740991'
#   }
# ]

# for holding in holdings:
#   for key, value in holding.items():
#     print ("holding: %s %s" %(key, value))


# trade_offer = {
# "description": "Offer self transfer RTC to RTCTrade",
# "label": "RTC2RTCTrade",
# "rules": [
#     {
#         "type": "EXCHANGE_LIMITED_TO_ACCOUNTS",
#         "value": [
#             ""
#         ]
#     }
# ],
# "source": "",
# "sourceQuantity": 1,
# "target": "",
# "targetQuantity": 1
# }
# trade_offer['rules'][0]['value'] = "KADJLFKJDF"
# # print(json.dumps(trade_offer, indent=4, sort_keys=True))
# t = json.dumps(trade_offer, indent=4, sort_keys=True)
# body = b''.join([t.encode()])
# print('Init New Holding for Account NEW BODY %s' % body)

# x = 'abc'

# test={}
# test['a'] = 1
# test['b'] = 2
# test['c'] = 3
# test[x] = 3
# print(json.dumps(test, indent=4, sort_keys=True))
