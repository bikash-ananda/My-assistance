const path = require("node:path");

const standalone = path.resolve(__dirname, "..", ".next", "standalone");
process.env.HOSTNAME = "127.0.0.1";
process.env.PORT = "3000";
process.chdir(standalone);
require(path.join(standalone, "server.js"));
