// algorandUtils.js
import algosdk from "algosdk";

const algodClient = new algosdk.Algodv2(
  '',
  'https://testnet-api.algonode.cloud',
  ''
);

export async function checkBalance(address) {
  try {
    const accountInfo = await algodClient.accountInformation(address).do();
    const microAlgos = Number(accountInfo.amount);
    console.log(microAlgos);
    return microAlgos / 1e6;
  } catch (err) {
    console.error("❌ Error fetching balance:", err);
    throw err;
  }
}

export async function createTestWallet() {
  const account = algosdk.generateAccount();
  const mnemonic = algosdk.secretKeyToMnemonic(account.sk);

  // console.log("\n🔐 Algorand Test Wallet Created");
  // console.log(`🪪 Address: ${account.addr}`);
  // console.log(`📝 Mnemonic:\n${mnemonic}`);
  // console.log("\n🌊 Fund it via TestNet faucet:");
  // console.log("https://bank.testnet.algorand.network\n");

  return JSON.stringify({
    address: `${account.addr}`,
    mnemonic: mnemonic
  }, null, 2)
}

export async function sendAlgo({ fromMnemonic, toAddress, amount }) {
  try {

    if (!fromMnemonic || !toAddress) {
      throw new Error("Both fromMnemonic and toAddress are required");
    }

    const sender = algosdk.mnemonicToSecretKey(fromMnemonic);

    if (!sender.addr) {
      throw new Error("Invalid fromMnemonic - failed to derive sender address");
    }

    if (typeof toAddress !== "string" || toAddress.trim() === "") {
      throw new Error("Invalid toAddress");
    }

    const params = await algodClient.getTransactionParams().do();

    const microAlgos = Math.round(amount * 1e6);

    // console.log("values");
    // console.log(`${sender.addr}`);
    // console.log(toAddress);
    // console.log(microAlgos);
    // console.log(params);

    const txn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
      sender: `${sender.addr}`,
      receiver: toAddress,
      amount: microAlgos, 
      closeRemainderTo: undefined,
      suggestedParams: params,
      note: undefined,
      lease: undefined,
      rekeyTo: undefined,

    });

    const signedTxn = txn.signTxn(sender.sk);
    const txResponse = await algodClient.sendRawTransaction(signedTxn).do();
    
    console.log("Transaction send response:", txResponse);
    
    const txId = txResponse.txid;
    if (!txId) {
      throw new Error("No transaction ID returned from algod");
    }
    
    const confirmedTxn = await algosdk.waitForConfirmation(algodClient, txId, 4);

    console.log("✅ Transaction confirmed in round", confirmedTxn["confirmed-round"]);

    return {
      txId,
      round: confirmedTxn["confirmed-round"],
    };
  } catch (err) {
    console.error("❌ Error sending Algos:", err);
    throw err;
  }
}
