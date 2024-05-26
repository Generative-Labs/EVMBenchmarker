from solcx import compile_source
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.contract.async_contract import AsyncContractConstructor
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware
from eth_account import Account
from eth_account.signers.local import LocalAccount
from ujson import loads
from asyncio import get_event_loop
from time import time
import statistics


Account.enable_unaudited_hdwallet_features()

EVM_NODE_URI = "your node URI here"

BATCH_TRANSFER_CONTRACT = ""

ERC20_CONTRACT = ""

# If you will testing RETH, UNCOMMENT the following code snippet.
# bank_account: LocalAccount = Account.from_mnemonic(
#     "test test test test test test test test test test test junk",

#     account_path=f"m/44'/60'/0'/0/{0}",
# )


# If you will testing EVMOS, UNCOMMENT the following code snippet.
# bank_account: LocalAccount = Account.from_mnemonic(
#     "gesture inject test cycle original hollow east ridge hen combine junk child bacon zero hope comfort vacuum milk pitch cage oppose unhappy lunar seat",
#     account_path=f"m/44'/60'/0'/0/{0}",
# )

# If you will testing Frontier, UNCOMMENT the following code snippet.
# bank_account: LocalAccount = Account.from_key(
#     "0x99B3C12287537E38C90A9219D4CB074A89A16E9CDB20BF85728EBD97C343E342"
# )


print(bank_account.address)


def compile_source_file(file_path):
    with open(file_path, "r") as f:
        source = f.read()

    return compile_source(source, output_values=["abi", "bin"])


def load_compiled_contract(file_path: str):
    with open(file_path, "r") as f:
        return loads(f.read())


async def deploy_contract_by_file(contract_file: str):
    compiled_contract = compile_source_file(f"contracts/{contract_file}")

    contract_id, contract_interface = compiled_contract.popitem()
    bytecode = contract_interface["bin"]
    abi = contract_interface["abi"]

    tx_hash: AsyncContractConstructor = (
        await web3_client.eth.contract(abi=abi, bytecode=bytecode)
        .constructor()
        .transact()
    )

    receipt = await web3_client.eth.wait_for_transaction_receipt(tx_hash)
    print("Contract Address:", receipt["contractAddress"])
    return receipt["contractAddress"], abi


async def deploy_contract(abi, bytecode):
    tx_hash: AsyncContractConstructor = (
        await web3_client.eth.contract(abi=abi, bytecode=bytecode)
        .constructor()
        .transact()
    )

    address = await web3_client.eth.get_transaction_receipt(tx_hash)["contractAddress"]
    return address


async def deploy_compiled_contract(compiled_contract: str = "compiled_ERC20.json"):
    COMPILED_CONTRACT: dict = load_compiled_contract(f"contracts/{compiled_contract}")

    ABI = COMPILED_CONTRACT.get("abi")
    BYTECODE = COMPILED_CONTRACT.get("bytecode")
    tx_hash: AsyncContractConstructor = (
        await web3_client.eth.contract(abi=ABI, bytecode=BYTECODE)
        .constructor()
        .transact()
    )

    receipt = await web3_client.eth.wait_for_transaction_receipt(tx_hash)
    print("Deployed Compiled Contract Address:", receipt["contractAddress"])
    return receipt["contractAddress"], ABI


web3_client = AsyncWeb3(AsyncHTTPProvider(EVM_NODE_URI))

web3_client.eth.default_account = bank_account.address

# print(get_compilable_solc_versions())

# The flow of benchmark (ERC20)
"""
0. create a lot of accounts, then send native token to them (via Contract).
1. deploy the ERC20 contract to test node, the contract which you just deployed will transfer all funds to creator(bank account).
2. use bank account to transfer ERC20 token to every account.
4. transfer ERC20 token to random account, via every one of accounts which created in step 0.
"""


# install_solc("0.8.24", True)


async def create_accounts(num: int) -> list[LocalAccount]:
    accounts = []
    for _ in range(num):
        acc = web3_client.eth.account.create()
        accounts.append(acc)
    return accounts


async def transfer_native_token_to_accounts(
    batch_transfer_contract: str,
    batch_transfer_contract_abi,
    accounts: list[LocalAccount],
    amount: float = 0.01,
):
    # nonce = await web3_client.eth.get_transaction_count(bank_account.address)
    batch_transfer = web3_client.eth.contract(
        abi=batch_transfer_contract_abi, address=batch_transfer_contract
    )

    print("batch_transfer_contract:", batch_transfer_contract)

    print(f"Accounts totaly: {len(accounts)}")

    # transfer to contract
    tx = await web3_client.eth.send_transaction(
        {
            "from": bank_account.address,
            "value": web3_client.to_wei(20, "ether"),
            "to": batch_transfer_contract,
        }
    )
    print("Transfer to contract TX:", hex(int.from_bytes(tx)))
    await web3_client.eth.wait_for_transaction_receipt(tx)

    transfer_to = []
    for acc in accounts:
        # print(acc.address)
        transfer_to.append(acc.address)
        if len(transfer_to) == 1000:  # 500 for RETH, 200 for EVMOS
            tx_hash = await batch_transfer.functions.transfers(
                transfer_to, int(amount * 10**18)
            ).transact()
            print("Transfer to accounts TX:", hex(int.from_bytes(tx_hash)))
            receipt = await web3_client.eth.wait_for_transaction_receipt(tx_hash)
            # print(
            #     ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",
            #     receipt,
            # )
            transfer_to.clear()


async def transfer_erc20_token_to_accounts(
    token_contract_address: str,
    token_contract_abi,
    accounts: list[LocalAccount],
    amount: float = 0.01,
):
    # nonce = await web3_client.eth.get_transaction_count(bank_account.address)
    token_contract = web3_client.eth.contract(
        abi=token_contract_abi, address=token_contract_address
    )

    print(
        "Bank balance(ERC20):",
        await token_contract.functions.balanceOf(bank_account.address).call(),
    )

    print("token_contract:", token_contract_address)

    print(f"Accounts totaly: {len(accounts)}")

    transfer_to = []
    for acc in accounts:
        # print(acc.address)
        transfer_to.append(acc.address)
        if len(transfer_to) == 1000:
            tx_hash = await token_contract.functions.batch_transfer(
                transfer_to, int(amount * 10**18)
            ).transact()
            print("Transfer ERC20 to accounts TX:", hex(int.from_bytes(tx_hash)))
            receipt = await web3_client.eth.wait_for_transaction_receipt(tx_hash)
            # print(
            #     ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",
            #     receipt,
            # )
            transfer_to.clear()
    return not transfer_to, token_contract


async def main(test_count: 1):
    tps_coll = []

    for i in range(test_count):
        accounts, token_contract = await prepare()

        txs = []

        start_time = 0.0

        for acc in accounts:
            tx = await token_contract.functions.transfer(
                web3_client.eth.account.create().address, int(0.0001 * 10**18)
            ).build_transaction(
                {
                    "from": acc.address,
                    "nonce": 0,
                }
            )

            signed_tx = web3_client.eth.account.sign_transaction(
                tx, private_key=acc.key
            )

            if accounts.index(acc) == 0:
                start_time = time()

            tx_hash = await web3_client.eth.send_raw_transaction(
                signed_tx.rawTransaction
            )
            txs.append(tx_hash)

        total_txs = len(txs)

        gas_used_coll = []

        # while len(txs) > 0:
        #     for tx_hash in txs:
        #         try:
        #             receipt = await web3_client.eth.get_transaction_receipt(tx_hash)
        #             if receipt.status == 1:
        #                 gas_used_coll.append(
        #                     receipt.gasUsed * receipt.effectiveGasPrice
        #                 )
        #                 txs.remove(tx_hash)
        #         except:
        #             continue

        duration = 0.0

        while True:
            try:
                receipt = await web3_client.eth.get_transaction_receipt(txs[-1])
                if receipt.status == 1:
                    duration = time() - start_time
                    break
            except:
                continue

        tps = total_txs / duration

        print("\r\n")
        print(
            f"Round {i}:  Duration: {duration}, total txs: {total_txs}, TPS:{tps} , avg Gas: {statistics.mean(gas_used_coll)}\r\n"
        )

        tps_coll.append(tps)
    print(f"{test_count}Rounds avg TPS: {statistics.mean(tps_coll)}")


async def prepare(accounts_num: int = 1000):
    web3_client.middleware_onion.add(
        await async_construct_sign_and_send_raw_middleware(bank_account)
    )

    if not BATCH_TRANSFER_CONTRACT:
        batch_transfer_contract, abi = await deploy_contract_by_file(
            "batch_transfer.sol"
        )
    else:
        compiled_contract = compile_source_file("contracts/batch_transfer.sol")
        _, contract_interface = compiled_contract.popitem()
        abi = contract_interface["abi"]
        batch_transfer_contract = BATCH_TRANSFER_CONTRACT
    accounts = await create_accounts(accounts_num)
    await transfer_native_token_to_accounts(batch_transfer_contract, abi, accounts)

    if not ERC20_CONTRACT:
        token_contract_address, token_abi = await deploy_compiled_contract()
    else:
        COMPILED_CONTRACT: dict = load_compiled_contract(
            "contracts/compiled_ERC20.json"
        )

        token_abi = COMPILED_CONTRACT.get("abi")
        token_contract_address = ERC20_CONTRACT

    _, token_contract = await transfer_erc20_token_to_accounts(
        token_contract_address, token_abi, accounts
    )

    return accounts, token_contract


if __name__ == "__main__":
    loop = get_event_loop()
    loop.run_until_complete(main(5))
