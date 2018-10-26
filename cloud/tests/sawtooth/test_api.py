#!/usr/local/bin/python3.6
import json
import sys
import os
import asyncio
import base64
import aiohttp
import time

from enum import Flag, auto

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
                    toPublicKey
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

        val = self.getExchangeLimitedToAccount(toPublicKey)
        if not None in (val, toPublicKey):
            vals.append(val)

        return vals


accounts = [
    {'email': 'admin@retc.io', 'password': 'b21izJw23qA'},
    {'email': 'testuserA@retc.io', 'password': 'TestW5XOfMoJy30'},
    {'email': 'testuserB@retc.io', 'password': 'TestW5XOfMoJy30'}
]
TOKENS = {}
URL = 'http://127.0.0.1:8041/api'


def sync_wait(future):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(future)


def get_close_offer(offer_id):
    return ('offers/%s/close' % offer_id, 'patch')


# def get_accept_offer_payload(offer_id, count, target):
#     return ('offers/%s/accept' % offer_id, 'patch', {"count": count, "target": target})


def get_accept_offer_payload(offer_id, count, source, target):
    """

    :param offer_id: the ID for the offering trade
    :param count: the unit count for transaction
    :param source: the source holding ID for the exchanged asset required in the offer
    :param target: the holding target ID of where exchanged asset will be placed
    :return: (api, method, payload)
    """
    return ('offers/%s/accept' % offer_id, 'patch', {"count": count, 'source': source, "target": target})


def get_offer_payload(label, description, source, target, sourceQuantity, targetQuantity, rules, toPublicKey=None):
    offerPayload = {
        "description": description,
        "label": label,
        "rules": [
        ],
        "source": source,
        "sourceQuantity": sourceQuantity,
        "target": target,
        "targetQuantity": targetQuantity
    }
    rules.getRules(offerPayload['rules'], toPublicKey)
    return ('offers', 'post', offerPayload)


# print(getOfferPayload('label', 'description', 'source', 'target',
#             'sourceQuantity', 'targetQuantity','publicKey'))
def createREU4REROffer(adminAccount, userAccount, sourceQuantity, targetQuantity):
    rules = Rule.EXCHANGE_ONCE | Rule.EXCHANGE_LIMITED_TO_ACCOUNTS
    return get_offer_payload('REU4RER', 'One time exchange offer of REU for RER',
                             get_account_holding_by_asset('REU', adminAccount)['id'],
                             get_account_holding_by_asset('RER', adminAccount)['id'], sourceQuantity, targetQuantity,
                             rules,
                             userAccount['publicKey'])


def createREU4RTCOffer(userAccount, sourceQuantity, targetQuantity, toPublicKey):
    rules = Rule.EXCHANGE_LIMITED_TO_ACCOUNTS
    return get_offer_payload('REU4RTC', 'Exchange offer of REU for RTC',
                             get_account_holding_by_asset('REU', userAccount)['id'],
                             get_account_holding_by_asset('RTC', userAccount)['id'], sourceQuantity, targetQuantity,
                             rules,
                             toPublicKey)


def createRTC4REUOffer(userAccount, sourceQuantity, targetQuantity):
    rules = Rule.EXCHANGE_LIMITED_TO_ACCOUNTS
    return get_offer_payload('REU4RTC', 'Exchange offer of RTC for REU',
                             get_account_holding_by_asset('RTC', userAccount)['id'],
                             get_account_holding_by_asset('REU', userAccount)['id'], sourceQuantity, targetQuantity,
                             rules,
                             userAccount['publicKey'])


def get_account_holding_by_asset(asset, account):
    for holding in account['holdings']:
        if holding['asset'] == asset:
            return holding


def get_account_holding_by_label(label, account):
    for holding in account['holdings']:
        if holding['label'] == label:
            return holding


def get_account_offer(label, account):
    for offer in account['offers']:
        if offer['label'] == label:
            return offer


'''Seller Trading'''


def create_init_sell_order(adminAccount, userAccount, sourceREUQuantity):
    '''
    Do all validation before calling.

    :param adminAccount:
    :param userAccount:
    :param sourceREUQuantity:
    :return: the offer for REU by Admin.
    '''
    (api, method, payload) = createREU4REROffer(adminAccount, userAccount, sourceREUQuantity, sourceREUQuantity)
    result = sync_send_api(api, method, payload, adminAccount['token'])

    (api, method, payload) = get_accept_offer_payload(result['id'], 1,
                                                      get_account_holding_by_label('RER', userAccount)['id'],
                                                      get_account_holding_by_label('REU', userAccount)['id'])
    sync_send_api(api, method, payload, userAccount['token'])

    (api, method) = get_close_offer(result['id'])
    sync_send_api(api, method, token=adminAccount['token'])
    return result


def create_sell_order(adminAccount, userAccount, sourceREUQuantity, targetRTCPrice, toPublicKey):
    try:
        create_init_sell_order(adminAccount, userAccount, sourceREUQuantity)
        # Create Seller offer to sell
        (api, method, payload) = createREU4RTCOffer(userAccount, 100, targetRTCPrice, toPublicKey)  # 100REU = 1kWh
        result = sync_send_api(api, method, payload, userAccount['token'])
        return result
    except AssertionError as e:
        # TODO: Add more error handling
        pass
    except Exception as e:
        pass


def buyer_accept_seller_order(offer_id, count, buyerAccount):
    try:
        (api, method, payload) = get_accept_offer_payload(offer_id, count,
                                                          get_account_holding_by_label('RTC', buyerAccount)['id'],
                                                          get_account_holding_by_label('REUR', buyerAccount)['id'])
        sync_send_api(api, method, payload, buyerAccount['token'])
    # TODO: Close Offer if quantity error
    except AssertionError as e:
        # TODO: Add more error handling
        pass


def seller_close_offer(sellOfferId, adminOfferId, sellerAccount):
    try:
        (api, method) = get_close_offer(sellOfferId)
        sync_send_api(api, method, token=sellerAccount['token'])

        if (get_account_holding_by_label('REU', sellerAccount)['quantity'] == 0):
            return

        (api, method, payload) = get_accept_offer_payload(adminOfferId,
                                                          get_account_holding_by_label('REU', sellerAccount)[
                                                              'quantity'],
                                                          get_account_holding_by_label('REU', sellerAccount)['id'],
                                                          get_account_holding_by_label('RRE', sellerAccount)['id'])
        sync_send_api(api, method, payload, sellerAccount['token'])
    except AssertionError as e:
        # TODO: Add more error handling
        pass


def test_sell_offer():
    global accounts
    (price, quantity, adminAccount, sellerAccount, buyerAccount) = (
        25, 20 * 100, accounts[0], accounts[1], accounts[2])  # $0.25 for 20kWh
    _sellerOrigREUQuantity = get_account_holding_by_label('REU', sellerAccount)['quantity']
    _ = create_init_sell_order(adminAccount, sellerAccount, quantity)
    _account = sync_get_account_info(sellerAccount)
    _sellerREUQuantity = get_account_holding_by_label('REU', _account)['quantity']
    assert _sellerREUQuantity == _sellerOrigREUQuantity + quantity

    order = create_sell_order(adminAccount, sellerAccount, quantity, price, buyerAccount['publicKey'])
    time.sleep(1)
    _account = sync_get_account_info(sellerAccount)
    _sellerREUQuantity = get_account_holding_by_label('REU', _account)['quantity']
    _buyerAccountBefore = sync_get_account_info(buyerAccount)
    _buyerRTCQuantity = get_account_holding_by_label('RTC', _buyerAccountBefore)['quantity']
    # Accepting order in increment of 1kWH
    for count in range(1, 3):
        buyer_accept_seller_order(order['id'], 1, buyerAccount)
        time.sleep(2)
        _account = sync_get_account_info(buyerAccount)
        assert get_account_holding_by_label('RTC', _account)['quantity'] == _buyerRTCQuantity - (count * price)
        assert get_account_holding_by_label('REUR', _account)['quantity'] == \
               get_account_holding_by_label('REUR', _buyerAccountBefore)['quantity'] + (count * 100)

        _account = sync_get_account_info(sellerAccount)
        assert get_account_holding_by_label('REU', _account)['quantity'] == _sellerREUQuantity - (count * 100)

    sync_refresh_accounts()
    seller_close_offer(order['id'], get_account_offer('RRE4REU Refund',adminAccount)['id'], accounts[1])
    sync_refresh_accounts()
    # assert get_account_holding_by_label('RRE', accounts[2])['quantity'] == 5 * 100


'''Buyer Trading'''


def seller_accept_buyer_offer(offer_id, count, adminAccount, sellerAccount, sourceREUQuantity):
    try:
        if get_account_holding_by_label('REU', sellerAccount)[
            'quantity'] == 0:  # Init if first time because seller REU is empty
            create_init_sell_order(adminAccount, sellerAccount, sourceREUQuantity)

        (api, method, payload) = get_accept_offer_payload(offer_id, count,
                                                          get_account_holding_by_label('RTC', sellerAccount)['id'],
                                                          get_account_holding_by_label('REU', sellerAccount)['id'])
        sync_send_api(api, method, payload, sellerAccount['token'])
    # TODO: Close Offer if quantity error
    except AssertionError as e:
        # TODO: Add more error handling
        pass


def create_buy_order(offer_id, price, rtcQuantity, buyerAccount):
    buyer_transfer_rtc_to_trade(offer_id, rtcQuantity, buyerAccount)
    create_buy_offer(offer_id, price, buyerAccount)


def buyer_transfer_rtc_to_trade(offer_id, rtcQuantity, buyerAccount):
    (api, method, payload) = get_accept_offer_payload(offer_id, rtcQuantity,
                                                      get_account_holding_by_label('RTC', buyerAccount)['id'],
                                                      get_account_holding_by_label('RTCTrade', buyerAccount)['id'])
    result = sync_send_api(api, method, payload, buyerAccount['token'])
    return result


def buyer_return_trade_to_rtc(offer_id, buyerAccount):
    (api, method, payload) = get_accept_offer_payload(offer_id,
                                                      get_account_holding_by_label('RTC', buyerAccount)['quantity'],
                                                      get_account_holding_by_label('RTC', buyerAccount)['id'],
                                                      get_account_holding_by_label('RTCTrade', buyerAccount)['id'])
    result = sync_send_api(api, method, payload, buyerAccount['token'])
    return result


def create_buy_offer(offer_id, price, buyerAccount):
    # Create Buyer offer to buy
    (api, method, payload) = createRTC4REUOffer(buyerAccount, price, 100)  # 100REU = 1kWh
    result = sync_send_api(api, method, payload, buyerAccount['token'])
    return result


# def test_buy_offer(offer_id, price, buyerAccount):


def sync_send_api(url, method, data={}, token=None):
    return sync_wait(send_api(url, method, data, token))


async def send_api(url, method, data={}, token=None):
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


def sync_get_account_info(account):
    (uid, token) = (account['publicKey'], account['token'])
    return sync_wait(get_account_info(uid, token))


async def get_account_info(account):
    (uid, token) = (account['publicKey'], account['token'])
    return await get_account_info(uid, token)


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


async def login(account):
    return (await send_api('authorization', 'post', account))['authorization']


def sync_refresh_accounts():
    return sync_wait(refresh_accounts())


async def refresh_accounts():
    time.sleep(1)
    global accounts

    for idx, account in enumerate(accounts):
        _token = account['token']
        userObj = getUserInfo(_token)

        _account = await get_account_info(userObj['public_key'], _token)
        accounts[idx] = {**accounts[idx], **_account}

        _offers = await get_account_offers(_token)
        accounts[idx] = {**accounts[idx], 'offers': _offers}


def getUserInfo(_token):
    _user = _token.split('.')[1]
    _user += "=" * ((4 - len(_user) % 4) % 4)
    user = base64.b64decode(_user)
    return json.loads(user)


async def init_login_accounts():
    global accounts

    for idx, account in enumerate(accounts):
        # _token = (await getAuth(val))['authorization']
        _token = await login(account)
        account['token'] = _token
        userObj = getUserInfo(_token)

        _account = await get_account_info(userObj['public_key'], _token)
        accounts[idx] = {**accounts[idx], **_account}

        _offers = await get_account_offers(_token)
        accounts[idx] = {**accounts[idx], 'offers': _offers}


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_login_accounts())
    try:
        test_sell_offer()
    except AssertionError as e:
        print(e)
        raise


main()

# async def main():
#     await init_login_accounts()
#     # print(json.dumps(accounts, indent=4, sort_keys=True))
#     test_sell_offer()


# if __name__ == "__main__":
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(main())

sys.exit(1)
