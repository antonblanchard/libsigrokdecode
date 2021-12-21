##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012-2013 Uwe Hermann <uwe@hermann-uwe.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from common.srdhelper import SrdIntEnum

# ...
fields = {
    # START field (indicates start or stop of a transaction)
    'START': {
        0b0000: 'Start of cycle for a target',
        0b0001: 'Reserved',
        0b0010: 'Grant for bus master 0',
        0b0011: 'Grant for bus master 1',
        0b0100: 'Reserved',
        0b0101: 'Reserved',
        0b0110: 'Reserved',
        0b0111: 'Reserved',
        0b1000: 'Reserved',
        0b1001: 'Reserved',
        0b1010: 'Reserved',
        0b1011: 'Reserved',
        0b1100: 'Reserved',
        0b1101: 'Start of cycle for a Firmware Memory Read cycle',
        0b1110: 'Start of cycle for a Firmware Memory Write cycle',
        0b1111: 'Stop/abort (end of a cycle for a target)',
    },
    # Cycle type / direction field
    # Bit 0 (LAD[0]) is unused, should always be 0.
    # Neither host nor peripheral are allowed to drive 0b11x0.
    'CT_DR': {
        0b0000: 'I/O read',
        0b0010: 'I/O write',
        0b0100: 'Memory read',
        0b0110: 'Memory write',
        0b1000: 'DMA read',
        0b1010: 'DMA write',
        0b1100: 'Reserved / not allowed',
        0b1110: 'Reserved / not allowed',
    },
    # SIZE field (determines how many bytes are to be transferred)
    # Bits[3:2] are reserved, must be driven to 0b00.
    # Neither host nor peripheral are allowed to drive 0b0010.
    'SIZE': {
        0b0000: '8 bits (1 byte)',
        0b0001: '16 bits (2 bytes)',
        0b0010: 'Reserved / not allowed',
        0b0011: '32 bits (4 bytes)',
    },
    # CHANNEL field (bits[2:0] contain the DMA channel number)
    'CHANNEL': {
        0b0000: '0',
        0b0001: '1',
        0b0010: '2',
        0b0011: '3',
        0b0100: '4',
        0b0101: '5',
        0b0110: '6',
        0b0111: '7',
    },
    # SYNC field (used to add wait states)
    'SYNC': {
        0b0000: 'Ready',
        0b0001: 'Reserved',
        0b0010: 'Reserved',
        0b0011: 'Reserved',
        0b0100: 'Reserved',
        0b0101: 'Short wait',
        0b0110: 'Long wait',
        0b0111: 'Reserved',
        0b1000: 'Reserved',
        0b1001: 'Ready more (DMA only)',
        0b1010: 'Error',
        0b1011: 'Reserved',
        0b1100: 'Reserved',
        0b1101: 'Reserved',
        0b1110: 'Reserved',
        0b1111: 'Reserved',
    },
}

Ann = SrdIntEnum.from_str('Ann', 'WARNING START CYCLE_TYPE ADDR TAR1 SYNC SERVER_DATA TAR2 LAD PERIPHERAL_DATA')

class Decoder(srd.Decoder):
    api_version = 3
    id = 'lpc'
    name = 'LPC'
    longname = 'Low Pin Count'
    desc = 'Protocol for low-bandwidth devices on PC mainboards.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['PC']
    channels = (
        {'id': 'lframe', 'name': 'LFRAME#', 'desc': 'Frame'},
        {'id': 'lclk',   'name': 'LCLK',    'desc': 'Clock'},
        {'id': 'lad0',   'name': 'LAD[0]',  'desc': 'Addr/control/data 0'},
        {'id': 'lad1',   'name': 'LAD[1]',  'desc': 'Addr/control/data 1'},
        {'id': 'lad2',   'name': 'LAD[2]',  'desc': 'Addr/control/data 2'},
        {'id': 'lad3',   'name': 'LAD[3]',  'desc': 'Addr/control/data 3'},
    )
    optional_channels = (
        {'id': 'lreset', 'name': 'LRESET#', 'desc': 'Reset'},
        {'id': 'ldrq',   'name': 'LDRQ#',   'desc': 'Encoded DMA / bus master request'},
        {'id': 'serirq', 'name': 'SERIRQ',  'desc': 'Serialized IRQ'},
        {'id': 'clkrun', 'name': 'CLKRUN#', 'desc': 'Clock run'},
        {'id': 'lpme',   'name': 'LPME#',   'desc': 'LPC power management event'},
        {'id': 'lpcpd',  'name': 'LPCPD#',  'desc': 'Power down'},
        {'id': 'lsmi',   'name': 'LSMI#',   'desc': 'System Management Interrupt'},
    )
    annotations = (
        ('warning', 'Warning'),
        ('start', 'Start'),
        ('cycle_type', 'Cycle-type/direction'),
        ('addr', 'Address'),
        ('tar1', 'Turn-around cycle 1'),
        ('sync', 'Sync'),
        ('server_data', 'Server Data'),
        ('tar2', 'Turn-around cycle 2'),
        ('lad', 'LAD bus'),
        ('peripheral_data', 'Peripheral Data'),
    )
    annotation_rows = (
        ('lad-vals', 'LAD bus', (Ann.LAD,)),
        ('server-vals', 'Server', (Ann.START, Ann.CYCLE_TYPE, Ann.ADDR, Ann.TAR1, Ann.SERVER_DATA)),
        ('periherals-vals', 'Peripheral', (Ann.SYNC, Ann.TAR2, Ann.PERIPHERAL_DATA)),
        ('warnings', 'Warnings', (Ann.WARNING,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'IDLE'

        self.lad = -1
        self.lframe = 1
        self.prev_lad = -1

        self.addr = 0
        self.data = 0

        self.cycle_type = -1
        self.cycle_count = 0

        self.ss_block = None
        self.ss_cycle = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    # Address and data fields are output as multicycle block
    def put_block(self, data):
        self.put(self.ss_block, self.samplenum, self.out_ann, data)

    # All other fields are output as a single cycle block
    def put_cycle(self, data):
        self.put(self.ss_cycle, self.samplenum, self.out_ann, data)

    def handle_get_start(self, lad_bits, lframe):
        # LAD[3:0]: START field (1 clock cycle).

        # The last value of LAD[3:0] before LFRAME# gets de-asserted is what
        # the peripherals must use. However, the host can keep LFRAME# asserted
        # multiple clocks, and we output all START fields that occur, even
        # though the peripherals are supposed to ignore all but the last one.
        self.put_cycle([Ann.START, [fields['START'][self.lad], 'START', 'St', 'S']])

        # Output a warning if LAD[3:0] changes while LFRAME# is low.
        if (self.prev_lad != -1 and self.prev_lad != self.lad):
            self.put_cycle([Ann.START, ['LAD[3:0] changed while LFRAME# was asserted']])

        self.prev_lad = self.lad

        # LFRAME# is asserted (low). Wait until it gets de-asserted again
        # (the host is allowed to keep it asserted multiple clocks).
        if lframe != 1:
            return

        self.state = 'GET CT/DR'

    def handle_get_ct_dr(self, lad_bits):
        # LAD[3:0]: Cycle type / direction field (1 clock cycle).

        self.cycle_type = fields['CT_DR'].get(self.lad, 'Reserved / unknown')

        if 'Reserved' in self.cycle_type:
            self.put_cycle([Ann.WARNING, ['Invalid cycle type (%s)' % lad_bits]])
            self.state = 'IDLE'
            return

        self.put_cycle([Ann.CYCLE_TYPE, ['Cycle type: %s' % self.cycle_type, "%s" % self.cycle_type]])

        if self.cycle_type in ('DMA read', 'DMA write'):
            self.put_cycle([Ann.WARNING, ['DMA cycle decoding not supported']])
            self.state = 'IDLE'
            return

        self.state = 'GET ADDR'
        self.ss_block = self.samplenum
        self.addr = 0
        self.cycle_count = 0

    def handle_get_addr(self, lad_bits):
        # LAD[3:0]: ADDR field (4/8/0 clock cycles).

        # I/O cycles: 4 ADDR clocks. Memory cycles: 8 ADDR clocks.
        if self.cycle_type in ('I/O read', 'I/O write'):
            addr_nibbles = 4 # Address is 16bits.
        elif self.cycle_type in ('Memory read', 'Memory write'):
            addr_nibbles = 8 # Address is 32bits.
        else:
            # Should never have got here for a DMA cycle
            raise Exception('Invalid cycle_type: %s' % self.cycle_type)

        # Addresses are driven MSN-first.
        offset = ((addr_nibbles - 1) - self.cycle_count) * 4
        self.addr |= (self.lad << offset)

        # Continue if we haven't seen all ADDR cycles, yet.
        if (self.cycle_count < addr_nibbles - 1):
            self.cycle_count += 1
            return

        s = 'Address: 0x%%0%dx' % addr_nibbles
        self.put_block([Ann.ADDR, [s % self.addr]])

        if self.cycle_type in ('I/O write', 'Memory write'):
            self.state = 'GET DATA'
            self.ss_block = self.samplenum
            self.cycle_count = 0
        else:
            self.state = 'GET TAR'
            self.cycle_count = 0

    def handle_get_tar(self, lad_bits):
        # LAD[3:0]: First TAR (turn-around) field (2 clock cycles).

        self.put_cycle([Ann.TAR1, ['TAR, cycle %d: %s' % (self.cycle_count, lad_bits)]])

        # On the first TAR clock cycle LAD[3:0] is driven to 1111 by
        # either the host or peripheral. On the second clock cycle,
        # the host or peripheral tri-states LAD[3:0], but its value
        # should still be 1111, due to pull-ups on the LAD lines.
        if lad_bits != '1111':
            self.put_cycle([Ann.WARNING, ['TAR, cycle %d: %s (expected 1111)' % \
                           (self.cycle_count, lad_bits)]])

        if (self.cycle_count != 1):
            self.cycle_count += 1
            return

        self.cycle_count = 0
        self.state = 'GET SYNC'

    def handle_get_sync(self, lad_bits):
        # LAD[3:0]: SYNC field (1-n clock cycles).

        sync_type = fields['SYNC'].get(self.lad, 'Reserved / unknown')

        if 'Reserved' in sync_type:
            self.put_cycle([Ann.WARNING, ['SYNC %s (reserved value)' % sync_type]])

        self.put_cycle([Ann.SYNC, ['SYNC: %s' % sync_type]])

        # Long or short wait
        if 'wait' in sync_type:
            return

        if self.cycle_type in ('I/O write', 'Memory write'):
            self.state = 'GET TAR2'
            self.cycle_count = 0
        else:
            self.state = 'GET DATA'
            self.cycle_count = 0
            self.ss_block = self.samplenum

    def handle_get_data(self, lad_bits):
        # LAD[3:0]: DATA field (2 clock cycles).

        # Data is driven LSN-first.
        if (self.cycle_count == 0):
            self.data = self.lad
        elif (self.cycle_count == 1):
            self.data |= (self.lad << 4)
        else:
            raise Exception('Invalid cycle_count: %d' % self.cycle_count)

        if (self.cycle_count != 1):
            self.cycle_count += 1
            return

        if self.cycle_type in ('I/O write', 'Memory write'):
            self.put_block([Ann.SERVER_DATA, ['DATA: 0x%02x' % self.data]])
        else:
            self.put_block([Ann.PERIPHERAL_DATA, ['DATA: 0x%02x' % self.data]])

        if self.cycle_type in ('I/O write', 'Memory write'):
            self.state = 'GET TAR'
            self.cycle_count = 0
        else:
            self.state = 'GET TAR2'
            self.cycle_count = 0

    def handle_get_tar2(self, lad_bits):
        # LAD[3:0]: Second TAR field (2 clock cycles).

        self.put_cycle([Ann.TAR2, ['TAR, cycle %d: %s' % (self.cycle_count, lad_bits)]])

        # On the first TAR clock cycle LAD[3:0] is driven to 1111 by
        # either the host or peripheral. On the second clock cycle,
        # the host or peripheral tri-states LAD[3:0], but its value
        # should still be 1111, due to pull-ups on the LAD lines.
        if lad_bits != '1111':
            self.put_cycle([Ann.WARNING, ['TAR, cycle %d: %s (expected 1111)'
                           % (self.cycle_count, lad_bits)]])

        if (self.cycle_count != 1):
            self.cycle_count += 1
            return

        self.cycle_count = 0
        self.state = 'IDLE'

    def handle_abort(self, lad_bits):
        # Go back to idle once lframe is no longer asserted
        if self.lframe == 1:
            self.state = 'IDLE'
            return

        if lad_bits == '1111':
            self.put_cycle([Ann.WARNING, ['ABORT']])

        return

    def decode(self):
        # When idle, look for lframe low (asserted) and rising LCLK edge
        # This allows us to skip over rising clock edges when idle
        idle_conditions = [{0: 'l', 1: 'r'}]
        # When not idle, only look for rising LCLK edges. The LPC clock
        # is the same as the PCI clock (which is sampled at rising edges).
        non_idle_conditions = [{1: 'r'}]
        while True:
            if self.state == 'IDLE':
                pins = self.wait(idle_conditions)
            else:
                pins = self.wait(non_idle_conditions)

            # Get individual pin values into local variables.
            (lframe, lclk, lad0, lad1, lad2, lad3) = pins[:6]
            (lreset, ldrq, serirq, clkrun, lpme, lpcpd, lsmi) = pins[6:]

            # Store LAD[3:0] bit values (one nibble) in local variables.
            # Most (but not all) states need this.
            if self.state != 'IDLE':
                lad_bits = '{:04b}'.format(self.lad)
                self.put_cycle([Ann.LAD, ['%s' % lad_bits]])

            # TODO: Need to implement DMA and firmware cycle decode

            # At any stage, if lframe is asserted with LAD=1111, then the
            # transaction is aborted
            if self.lframe == 0 and lad_bits == '1111':
                self.state = 'ABORT'
            # If lframe is asserted any time after the start of the transaction,
            # the transaction is aborted. Instead of checking this in almost every
            # state, do it here.
            elif self.lframe == 0 and self.state not in ('IDLE', 'GET START'):
                self.put_cycle([Ann.WARNING, ['LFRAME asserted during transaction, likely an abort']])
                self.state = 'ABORT'

            # State machine
            if self.state == 'IDLE':
                # A valid LPC cycle starts with LFRAME# being asserted (low).
                if lframe != 0:
                    continue
                self.state = 'GET START'
                self.lad = -1
            elif self.state == 'GET START':
                self.handle_get_start(lad_bits, lframe)
            elif self.state == 'GET CT/DR':
                self.handle_get_ct_dr(lad_bits)
            elif self.state == 'GET ADDR':
                self.handle_get_addr(lad_bits)
            elif self.state == 'GET TAR':
                self.handle_get_tar(lad_bits)
            elif self.state == 'GET SYNC':
                self.handle_get_sync(lad_bits)
            elif self.state == 'GET DATA':
                self.handle_get_data(lad_bits)
            elif self.state == 'GET TAR2':
                self.handle_get_tar2(lad_bits)
            elif self.state == 'ABORT':
                self.handle_abort(lad_bits)

            # Save the cycle of the last lclk rising edge
            self.ss_cycle = self.samplenum

            # We operate on the LAD bits and lframe from the previous cycle
            self.lad = (lad3 << 3) | (lad2 << 2) | (lad1 << 1) | lad0
            self.lframe = lframe
