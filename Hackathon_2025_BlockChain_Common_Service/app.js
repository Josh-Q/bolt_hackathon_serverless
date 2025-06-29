import * as pkg from "./algorandUtils.js";

const { checkBalance, createTestWallet, sendAlgo } = pkg;

const HOUSE_KEYS = process.env.HOUSE_KEYS;
const HOUSE_MNEMONIC = process.env.HOUSE_MNEMONIC;

export const handler = async (event) => {
  const method = event.method;
  let body = event.body;

  if (body) {
    try {
      body = JSON.parse(event.body);  // 🔥 critical line
    } catch (e) {
      console.error('Invalid JSON body:', e);
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Invalid JSON body' }),
      };
    }
  } else {
    // fallback for direct Lambda-to-Lambda invoke
    body = event;
  }

  if (!method || !body) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Missing method or body" }),
    };
  }

  try {
    // Route by path and method
    if (method === "balance") {
      const { address } = body;
      if (!address || typeof address !== "string") {
        return {
          statusCode: 400,
          body: JSON.stringify({ error: "Missing or invalid 'address'" }),
        };
      }
      const balance = await checkBalance(address);
      return {
        statusCode: 200,
        body: JSON.stringify({ address, balance }),
      };
    }

    if (method === "create-wallet") {
      const testWallet = await createTestWallet();
      return {
        statusCode: 200,
        body: JSON.stringify({ testWallet }),
      };
    }

    if (method === "send_to_house") {
      const { fromMnemonic, amount } = body;

      const numericAmount = Number(amount);

      if (!fromMnemonic || isNaN(numericAmount)) {
        return {
          statusCode: 400,
          body: JSON.stringify({  error: "invalid mnomonic or bid amount" }),
        };
      }      

      const result = await sendAlgo({ fromMnemonic, toAddress:HOUSE_KEYS, amount });
      return {
        statusCode: 200,
        body: JSON.stringify(result),
      };
    }


    if (method === "send_to_user") {
      const { toAddress, amount } = body;

      const numericAmount = Number(amount);

      if (!toAddress || isNaN(numericAmount)) {
        return {
          statusCode: 400,
          body: JSON.stringify({ error: "invalid toAddress or bid amount" }),
        };
      }
      const result = await sendAlgo({ fromMnemonic:HOUSE_MNEMONIC, toAddress, amount });
      return {
        statusCode: 200,
        body: JSON.stringify(result),
      };
    }

    // If no matching route
    return {
      statusCode: 404,
      body: JSON.stringify({ error: "Route not found" }),
    };
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: err.message,
        details: err.message,
      }),
    };
  }
};
