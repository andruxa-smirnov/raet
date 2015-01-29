# -*- coding: utf-8 -*-
'''
Tests for messaging reliability

'''
# pylint: skip-file
# pylint: disable=C0103
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import os
import time
import tempfile
import shutil
from collections import deque

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer
from ioflo.base import storing
from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.road import estating, keeping, stacking, packeting, transacting

if sys.platform == 'win32':
    TEMPDIR = 'c:/temp'
    if not os.path.exists(TEMPDIR):
        os.mkdir(TEMPDIR)
else:
    TEMPDIR = '/tmp'

def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)

def tearDownModule():
    pass

class BasicTestCase(unittest.TestCase):
    """"""

    def setUp(self):
        self.store = storing.Store(stamp=0.0)
        self.timer = StoreTimer(store=self.store, duration=1.0)

        self.base = tempfile.mkdtemp(prefix="raet",  suffix="base", dir=TEMPDIR)

    def tearDown(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)

    def createRoadData(self,
                       base,
                       name='',
                       ha=None,
                       main=None,
                       auto=raeting.autoModes.never,
                       role=None,
                       kind=None, ):
        '''
        Creates odict and populates with data to setup road stack

        '''
        data = odict()
        data['name'] = name
        data['ha'] = ha
        data['main'] =  main
        data['auto'] = auto
        data['role'] = role if role is not None else name
        data['kind'] = kind
        data['dirpath'] = os.path.join(base, 'road', 'keep', name)
        signer = nacling.Signer()
        data['sighex'] = signer.keyhex
        data['verhex'] = signer.verhex
        privateer = nacling.Privateer()
        data['prihex'] = privateer.keyhex
        data['pubhex'] = privateer.pubhex

        return data

    def createRoadStack(self,
                        data,
                        uid=None,
                        ha=None,
                        main=None,
                        auto=None,
                        role=None,
                        kind=None,
                        period=None,
                        offset=None,):
        '''
        Creates stack and local estate from data with
        and overrides with parameters

        returns stack

        '''
        stack = stacking.RoadStack(store=self.store,
                                   name=data['name'],
                                   uid=uid,
                                   ha=ha or data['ha'],
                                   main=main if main is not None else data['main'],
                                   role=role if role is not None else data['role'],
                                   sigkey=data['sighex'],
                                   prikey=data['prihex'],
                                   auto=auto if auto is not None else data['auto'],
                                   kind=kind if kind is not None else data['kind'],
                                   dirpath=data['dirpath'],
                                   period=period,
                                   offset=offset,)

        return stack

    def join(self, initiator, correspondent, deid=None, duration=1.0,
                cascade=False):
        '''
        Utility method to do join. Call from test method.
        '''
        console.terse("\nJoin Transaction **************\n")
        if not initiator.remotes:
            initiator.addRemote(estating.RemoteEstate(stack=initiator,
                                                      fuid=0, # vacuous join
                                                      sid=0, # always 0 for join
                                                      ha=correspondent.local.ha))
        initiator.join(uid=deid, cascade=cascade)
        self.service(correspondent, initiator, duration=duration)

    def allow(self, initiator, correspondent, deid=None, duration=1.0,
                cascade=False):
        '''
        Utility method to do allow. Call from test method.
        '''
        console.terse("\nAllow Transaction **************\n")
        initiator.allow(uid=deid, cascade=cascade)
        self.service(correspondent, initiator, duration=duration)

    def alive(self, initiator, correspondent, duid=None, duration=1.0,
                cascade=False):
        '''
        Utility method to do alive. Call from test method.
        '''
        console.terse("\nAlive Transaction **************\n")
        initiator.alive(uid=duid, cascade=cascade)
        self.service(correspondent, initiator, duration=duration)

    def message(self, msgs, initiator, correspondent, duration=2.0):
        '''
        Utility to send messages both ways
        '''
        for msg in msgs:
            initiator.transmit(msg)

        self.service(initiator, correspondent, duration=duration)

    def flushReceives(self, stack):
        '''
        Flush any queued up udp packets in receive buffer
        '''
        stack.serviceReceives()
        stack.rxes.clear()

    def dupReceives(self, stack):
        '''
        Duplicate each queued up udp packet in receive buffer
        '''
        stack.serviceReceives()
        rxes = stack.rxes
        stack.rxes = deque()
        for rx in rxes:
            stack.rxes.append(rx) # one
            stack.rxes.append(rx) # and one more

    def service(self, main, other, duration=1.0):
        '''
        Utility method to service queues. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            other.serviceAll()
            main.serviceAll()
            if not (main.transactions or other.transactions):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def serviceStack(self, stack, duration=1.0):
        '''
        Utility method to service queues for one stack. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            stack.serviceAll()
            if not (stack.transactions):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def serviceStacks(self, stacks, duration=1.0):
        '''
        Utility method to service queues for list of stacks. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            for stack in stacks:
                stack.serviceAll()
            if all([not stack.transactions for stack in stacks]):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def serviceStacksDropRx(self, stacks, duration=1.0):
        '''
        Utility method to service queues for list of stacks. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            for stack in stacks:
                stack.serviceReceives()
                stack.rxes.clear()
                stack.serviceRxes()
                stack.process()
                stack.serviceAllTx()
            if all([not stack.transactions for stack in stacks]):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def testMessageWithDrops(self):
        '''
        Test message with packets dropped
        '''
        console.terse("{0}\n".format(self.testMessageWithDrops.__doc__))

        alphaData = self.createRoadData(name='alpha',
                                       base=self.base,
                                       auto=raeting.autoModes.once)
        keeping.clearAllKeep(alphaData['dirpath'])
        alpha = self.createRoadStack(data=alphaData,
                                     main=True,
                                     auto=alphaData['auto'],
                                     ha=None)

        betaData = self.createRoadData(name='other',
                                        base=self.base,
                                        auto=raeting.autoModes.once)
        keeping.clearAllKeep(betaData['dirpath'])
        beta = self.createRoadStack(data=betaData,
                                     main=True,
                                     auto=betaData['auto'],
                                     ha=("", raeting.RAET_TEST_PORT))

        console.terse("\nJoin *********\n")
        self.join(alpha, beta) # vacuous join fails because other not main
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, None)
            self.assertIs(remote.alived, None)

        console.terse("\nAllow *********\n")
        self.allow(alpha, beta)
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, True)
            self.assertIs(remote.alived, True)  # fast alive

        msgs = []
        bloat = []
        for i in range(300):
            bloat.append(str(i).rjust(100, " "))
        bloat = "".join(bloat)
        alphaMsg = odict(identifier="Green", bloat=bloat)
        msgs.append(alphaMsg)

        self.message(msgs, alpha, beta, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        betaMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(betaMsg, alphaMsg)

        for stack in [alpha, beta]:
            stack.server.close()
            stack.clearAllKeeps()



def runOne(test):
    '''
    Unittest Runner
    '''
    test = BasicTestCase(test)
    suite = unittest.TestSuite([test])
    unittest.TextTestRunner(verbosity=2).run(suite)

def runSome():
    '''
    Unittest runner
    '''
    tests =  []
    names = [
                'testMessageWithDrops',
            ]

    tests.extend(map(BasicTestCase, names))

    suite = unittest.TestSuite(tests)
    unittest.TextTestRunner(verbosity=2).run(suite)

def runAll():
    '''
    Unittest runner
    '''
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BasicTestCase))

    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__' and __package__ is None:

    #console.reinit(verbosity=console.Wordage.concise)

    #runAll() #run all unittests

    #runSome()#only run some

    runOne('testMessageWithDrops')