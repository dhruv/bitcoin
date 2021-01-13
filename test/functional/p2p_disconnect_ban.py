#!/usr/bin/env python3
# Copyright (c) 2014-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test node disconnect and ban behavior"""
import time

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_approx,
    assert_equal,
    assert_raises_rpc_error,
)

class DisconnectBanTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 2
        self.supports_cli = False

    def run_test(self):
        self.log.info("Connect nodes both way")
        # By default, the test framework sets up an addnode connection from
        # node 1 --> node0. By connecting node0 --> node 1, we're left with
        # the two nodes being connected both ways.
        # Topology will look like: node0 <--> node1
        self.connect_nodes(0, 1)

        self.log.info("Test setban and listbanned RPCs")

        self.log.info("setban: successfully ban single IP address")
        assert_equal(len(self.nodes[1].getpeerinfo()), 2)  # node1 should have 2 connections to node0 at this point
        self.nodes[1].setban(subnet="127.0.0.1", command="add")
        self.wait_until(lambda: len(self.nodes[1].getpeerinfo()) == 0, timeout=10)
        assert_equal(len(self.nodes[1].getpeerinfo()), 0)  # all nodes must be disconnected at this point
        assert_equal(len(self.nodes[1].listbanned()), 1)

        self.log.info("clearbanned: successfully clear ban list")
        self.nodes[1].clearbanned()
        assert_equal(len(self.nodes[1].listbanned()), 0)
        self.nodes[1].setban("127.0.0.0/24", "add")

        self.log.info("adding a subset ban creates a new ban entry")
        assert_equal(len(self.nodes[1].listbanned()), 1)
        self.nodes[1].setban("127.0.0.1", "add", 500)
        listbanned_response = self.nodes[1].listbanned()
        assert_equal(len(listbanned_response), 2)
        assert_equal(listbanned_response[1]["address"], "127.0.0.1/32")

        # Verify that relative bantime is correct
        now = int(time.time())
        assert_approx(listbanned_response[1]["banned_until"] - now, 10, 500)
        self.nodes[1].setban("127.0.0.1/32", "remove", 500)

        self.log.info("setban: fail to ban an invalid subnet")
        assert_raises_rpc_error(-30, "Error: Invalid IP/Subnet", self.nodes[1].setban, "127.0.0.1/42", "add")
        assert_equal(len(self.nodes[1].listbanned()), 1)  # still only one banned ip because 127.0.0.1/42 is invalid

        # Unbanning a non-banned subnet should succeed as user intent is accomplished
        self.log.info("setban remove: unban a non-banned subnet")
        self.nodes[1].setban("127.0.0.1", "remove")
        assert_equal(len(self.nodes[1].listbanned()), 1)

        self.log.info("setban remove: successfully unban subnet")
        self.nodes[1].setban("127.0.0.0/24", "remove")
        assert_equal(len(self.nodes[1].listbanned()), 0)
        self.nodes[1].clearbanned()
        assert_equal(len(self.nodes[1].listbanned()), 0)

        self.log.info("setban listbanned and removeall: ipv4 test")
        self.nodes[1].setban("127.0.0.1/16", "add")
        self.nodes[1].setban("127.0.0.1/24", "add")
        self.nodes[1].setban("127.0.0.1/32", "add")
        assert_equal(len(self.nodes[1].listbanned()), 3)
        assert_raises_rpc_error(-8, "Error: Invalid ip address", self.nodes[1].listbanned, "127.0.0.3/32")
        relevant_bans = self.nodes[1].listbanned("127.0.0.3")
        assert_equal({x["address"] for x in relevant_bans}, {"127.0.0.0/16", "127.0.0.0/24"})
        assert_raises_rpc_error(-8, "Error: setban removeall requires single ip address",
            self.nodes[1].setban, "127.0.0.3/32", "removeall")
        self.nodes[1].setban("127.0.0.3", "removeall")
        listbanned_response = self.nodes[1].listbanned()
        assert_equal(len(listbanned_response), 1)
        assert_equal(listbanned_response[0]["address"], "127.0.0.1/32")
        self.nodes[1].clearbanned()

        self.log.info("setban listbanned and removeall: ipv6 test")
        self.nodes[1].setban("2001:4d48:ac57:400:cacf:e9ff:fe1d:9c63/96", "add")
        self.nodes[1].setban("2001:4d48:ac57:400:cacf:e9ff:fe1d:9c63/112", "add")
        self.nodes[1].setban("2001:4d48:ac57:400:cacf:e9ff:fe1d:9c63/128", "add")
        assert_equal(len(self.nodes[1].listbanned()), 3)
        assert_raises_rpc_error(-8, "Error: Invalid ip address",
            self.nodes[1].listbanned, "2001:4d48:ac57:400:cacf:e9ff:fe1d:9c64/128")
        relevant_bans = self.nodes[1].listbanned("2001:4d48:ac57:400:cacf:e9ff:fe1d:9c64")
        assert_raises_rpc_error(-8, "Error: setban removeall requires single ip address",
            self.nodes[1].setban, "2001:4d48:ac57:400:cacf:e9ff:fe1d:9c64/128", "removeall")
        self.nodes[1].setban("2001:4d48:ac57:400:cacf:e9ff:fe1d:9c64", "removeall")
        listbanned_response = self.nodes[1].listbanned()
        assert_equal(len(listbanned_response), 1)
        assert_equal(listbanned_response[0]["address"], "2001:4d48:ac57:400:cacf:e9ff:fe1d:9c63/128")
        self.nodes[1].clearbanned()

        self.log.info("setban: test persistence across node restart")
        self.nodes[1].setban("127.0.0.0/32", "add")
        self.nodes[1].setban("127.0.0.0/24", "add")
        # Set the mocktime so we can control when bans expire
        old_time = int(time.time())
        self.nodes[1].setmocktime(old_time)
        self.nodes[1].setban("192.168.0.1", "add", 1)  # ban for 1 seconds
        self.nodes[1].setban("2001:4d48:ac57:400:cacf:e9ff:fe1d:9c63/19", "add", 1000)  # ban for 1000 seconds
        listBeforeShutdown = self.nodes[1].listbanned()
        assert_equal("192.168.0.1/32", listBeforeShutdown[2]['address'])
        # Move time forward by 3 seconds so the third ban has expired
        self.nodes[1].setmocktime(old_time + 3)
        assert_equal(len(self.nodes[1].listbanned()), 3)

        self.restart_node(1)

        listAfterShutdown = self.nodes[1].listbanned()
        assert_equal("127.0.0.0/24", listAfterShutdown[0]['address'])
        assert_equal("127.0.0.0/32", listAfterShutdown[1]['address'])
        assert_equal("/19" in listAfterShutdown[2]['address'], True)

        # Clear ban lists
        self.nodes[1].clearbanned()
        self.log.info("Connect nodes both way")
        self.connect_nodes(0, 1)
        self.connect_nodes(1, 0)

        self.log.info("Test disconnectnode RPCs")

        self.log.info("disconnectnode: fail to disconnect when calling with address and nodeid")
        address1 = self.nodes[0].getpeerinfo()[0]['addr']
        node1 = self.nodes[0].getpeerinfo()[0]['addr']
        assert_raises_rpc_error(-32602, "Only one of address and nodeid should be provided.", self.nodes[0].disconnectnode, address=address1, nodeid=node1)

        self.log.info("disconnectnode: fail to disconnect when calling with junk address")
        assert_raises_rpc_error(-29, "Node not found in connected nodes", self.nodes[0].disconnectnode, address="221B Baker Street")

        self.log.info("disconnectnode: successfully disconnect node by address")
        address1 = self.nodes[0].getpeerinfo()[0]['addr']
        self.nodes[0].disconnectnode(address=address1)
        self.wait_until(lambda: len(self.nodes[0].getpeerinfo()) == 1, timeout=10)
        assert not [node for node in self.nodes[0].getpeerinfo() if node['addr'] == address1]

        self.log.info("disconnectnode: successfully reconnect node")
        self.connect_nodes(0, 1)  # reconnect the node
        assert_equal(len(self.nodes[0].getpeerinfo()), 2)
        assert [node for node in self.nodes[0].getpeerinfo() if node['addr'] == address1]

        self.log.info("disconnectnode: successfully disconnect node by node id")
        id1 = self.nodes[0].getpeerinfo()[0]['id']
        self.nodes[0].disconnectnode(nodeid=id1)
        self.wait_until(lambda: len(self.nodes[0].getpeerinfo()) == 1, timeout=10)
        assert not [node for node in self.nodes[0].getpeerinfo() if node['id'] == id1]

if __name__ == '__main__':
    DisconnectBanTest().main()
