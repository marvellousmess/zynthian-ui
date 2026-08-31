#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchpad Pro MK2"
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import logging
from time import sleep, monotonic

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zyncoder.zyncore import lib_zyncore
from zyngine.zynthian_chain_manager import MAX_NUM_MIDI_CHANS
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer, zynthian_ctrldev_base
from zyngine.ctrldev.zynthian_ctrldev_base_extended import RunTimer, ButtonTimer, CONST
from zyngui import zynthian_gui_config
from zyngine.zynthian_signal_manager import zynsigman
from .zynthian_ctrldev_base_ui import ModeHandlerBase
import time
import multiprocessing as mp

# LAUNCHPAD CONSTANTS

# Mode definitions
MODE_SESSION = 0  # Grid launcher mode
MODE_NOTE = 1     # Note input mode
MODE_DEVICE = 2     # Device control mode
MODE_USER = 3    # User settings mode

# Button CC/Note numbers for mode selectors (top right) 
BTN_SESSION = 95   # CC number for session button
BTN_NOTE = 96      # CC number for note button
BTN_DEVICE = 97      # CC number for device button
BTN_USER = 98     # CC number for user button

BTN_UP = 0x5B
BTN_DOWN = 0x5C
BTN_LEFT = 0x5D
BTN_RIGHT = 0x5E

# Launchpad mode select buttons 
# BTN_SESSION = 0x5F
# BTN_NOTE = 0x60
# BTN_DEVICE = 0x61
# BTN_USER = 0x62

# Launchpad general mode select CC (ableton vs standalone)
MODE_SELECT_ABLETON_CC = "21 00"
MODE_SELECT_STANDALONE_CC = "21 01"

# Launchpad standalone sub-mode select CC
STANDALONE_SUB_SELECT_NOTE_CC = "2C 00"
STANDALONE_SUB_SELECT_DRUM_CC = "2C 01"
STANDALONE_SUB_SELECT_FADER_CC = "2C 02"
STANDALONE_SUB_SELECT_PROGRAMMER_CC = "2C 03"

# Launchpad ableton sub-mode select CC
ABLETON_SUB_SELECT_SESSION_CC = "22 00" 
ABLETON_SUB_SELECT_DRUM_CC = "22 01"
ABLETON_SUB_SELECT_CHROMATIC_CC = "22 02"
ABLETON_SUB_SELECT_USER_CC = "22 03" # Drum mode
ABLETON_SUB_SELECT_AUDIO_CC = "22 04" # Blank
ABLETON_SUB_SELECT_FADER_CC = "22 05"
ABLETON_SUB_SELECT_RECORD_ARM_CC = "22 06" # Session mode
ABLETON_SUB_SELECT_TRACK_SELECT_CC = "22 07" # Session mode
ABLETON_SUB_SELECT_MUTE_CC = "22 08" # Session mode
ABLETON_SUB_SELECT_SOLO_CC = "22 09" # Session mode
ABLETON_SUB_SELECT_VOLUME_CC = "22 0A" # Fader mode
ABLETON_SUB_SELECT_PAN_CC = "22 0B" # Fader mode
ABLETON_SUB_SELECT_SENDS_CC = "22 0C" # Fader mode
ABLETON_SUB_SELECT_STOP_CLIP_CC = "22 0D" # Session mode

# Launchpad left column buttons (PRO ONLY!) >> Launchpad mini/X - Change BTN_SHIFT to 0x13 and comment out BTN_PLAY_ROW_8
BTN_SHIFT = 0x50
BTN_CLICK = 0x46
BTN_UNDO = 0x3C
BTN_DELETE = 0x32
BTN_QUANTISE = 0x28
BTN_DUPLICATE = 0x1E
BTN_DOUBLE = BTN_PLAY = 0x14
BTN_RECORD = 0x0A

# Launchpad bottom row buttons (PRO ONLY!)
BTN_RECORD_ARM = 0x01
BTN_TRACK_SELECT = 0x02
BTN_MUTE = 0x03
BTN_SOLO = 0x04
BTN_VOLUME = 0x05
BTN_PAN = 0x06
BTN_SENDS= 0x07
BTN_STOP_CLIP = 0x08

# Volume and pan control levels as dictionary
FADER_CHANNEL = [0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C] # Same channel values across modes
VOL_SEND_LEVEL_CC = [0x00, 0x11, 0x22, 0x34, 0x46, 0x59, 0x6C, 0x7F]
PAN_LEVEL_CC = [0x00, 0x15, 0x2A, 0x3F, 0x40, 0x55, 0x6A, 0x7F] #[0x48, 0x49, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55] 

# Right column buttons (individual row playback)
BTN_PLAY_ROW_1 = 0x59
BTN_PLAY_ROW_2 = 0x4F
BTN_PLAY_ROW_3 = 0x45
BTN_PLAY_ROW_4 = 0x3B
BTN_PLAY_ROW_5 = 0x31
BTN_PLAY_ROW_6 = 0x27
BTN_PLAY_ROW_7 = 0x1D
BTN_PLAY_ROW_8 = 0x13

# Playback button column CCs top to bottom
BTN_PLAYBACK = [89, 79, 69, 59, 49, 39, 29, 19]
# Playback button column hex top to bottom
BTN_PLAYBACK_HEX = [0x59, 0x4F, 0x45, 0x3B, 0x31, 0x27, 0x1D, 0x13]

# MIDI channel events (first 4 bits), next 4 bits is the channel!
EV_NOTE_ON = 0x09
EV_NOTE_OFF = 0x08
EV_CC = 0x0B

# MIDI system events (first 8 bits)
EV_SYSEX = 0xF0
EV_CLOCK = 0xF8
EV_CONTINUE = 0xFB

# Create range as launchpad pro doesn't have sequential grid CC values
BTN_PAD_RANGE = [0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58,
                 0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 
                 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44,
                 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A,
                 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30,
                 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26,
                 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C,
                 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12,       
]

# Grid buttons for UI control
BTN_PAD_START = BTN_PAD_RANGE[0] # Original value 0x00 (launchpad = 0x29)
BTN_PAD_END = BTN_PAD_RANGE[-1] # Original value 0x27 (launchpad = 0x58)
BTN_PAD_29 = BTN_ALT = 0x4B
BTN_PAD_30 = BTN_METRONOME = 0x4C
BTN_PAD_31 = BTN_PAD_STEP = 0x4D
BTN_PAD_37 = BTN_OPT_ADMIN = 0x55
BTN_PAD_38 = BTN_MIX_LEVEL = 0x56
BTN_PAD_39 = BTN_CTRL_PRESET = 0x57
BTN_PAD_40 = BTN_ZS3_SHOT = 0x58
BTN_PAD_5 = BTN_PAD_LEFT = 0x2D
BTN_PAD_6 = BTN_PAD_DOWN = 0x2E
BTN_PAD_7 = BTN_PAD_RIGHT = 0x2F
BTN_PAD_8 = BTN_F4 = 0x30
BTN_PAD_13 = BTN_BACK_NO = 0x37
BTN_PAD_14 = BTN_PAD_UP = 0x38
BTN_PAD_15 = BTN_SEL_YES = 0x39
BTN_PAD_16 = BTN_F3 = 0x3A
BTN_PAD_21 = BTN_PAD_RECORD = 0x41
BTN_PAD_23 = BTN_PAD_STOP = 0x42
BTN_PAD_23 = BTN_PAD_PLAY = 0x43
BTN_PAD_24 = BTN_F2 = 0x44
BTN_PAD_32 = BTN_F1 = 0x4E
BTN_PAD_ZYNPOT_SWITCH_1 = 0x23
BTN_PAD_ZYNPOT_SWITCH_2 = 0x24
BTN_PAD_ZYNPOT_SWITCH_3 = 0x25
BTN_PAD_ZYNPOT_SWITCH_4 = 0x26

PRESSTYPE_DICT = {
    "short": "S",
    "bold": "B",
    "long": "L"
}

# LED modes for launchpad
LED_ON = 0x01
LED_PULSING = 0x03
LED_FLASHING = 0x02

UNROUTE_MIDI_CHAN = 0b0000000000000100  # Unroute channel 14

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchpad Pro MK2
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchpad_pro_mk2(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["Launchpad Pro IN 1"]
    driver_name = "Launchpad Pro MK2"
    driver_description = "Session launcher, note input, device control and fader modes"
    unroute_from_chains = True  # Prevent MIDI from reaching chains FIXME: Need to solve this so note mode can work
    # while avoiding sending MIDI to chains when in other modes
    need_wsled_state = True
    # IPC => multiprocessing.Value() object to share an integer variable across processes
    filter_enabled = mp.Value('i', 0)

    class LEDColors:
        # Launchpad LED Colours
        MODE_COLOUR = 29
        COLOR_WHITE = 3
        COLOR_YELLOW = 13
        COLOR_ORANGE = 96
        COLOR_DARK_ORANGE = 106
        COLOR_ALT_OFF = 3
        COLOR_ALT_ON = 78
        COLOR_STATE_1 = 9
        COLOR_STATE_2 = 81
        COLOR_PLAYING = COLOR_GREEN = 88
        COLOR_LIGHT_RED = 116 # 107
        COLOR_RED = 5
        COLOR_DEEP_RED = 6 # 60, 95 = HOT PINK, 56 = PEACH, 
        COLOR_LIGHT_BLUE = 91
        COLOR_BLUE = 79
        COLOR_DARK_GREEN = 76 # Match note mode directional button colours
        COLOR_DARK_BLUE = 46 # Match note mode directional button colours
        COLOR_DEEP_BLUE = 67     

    def __init__(self, state_manager, idev_in, idev_out=None):
        super().__init__(state_manager, idev_in, idev_out)
        self.mode = MODE_SESSION  # Current mode
        self.last_press = None
        self.note_octave = 3  # Starting octave for note mode
        self.cols = 8
        self.rows = 8
        # Feedback and device-mode handler integration
        self._feedback = FeedbackLEDs(self.idev_out)
        self._device_handler = DeviceHandler(self.state_manager, self._feedback, self.LEDColors)
        self.fader_mode = "volume"  # "volume", "pan", or "sends"

    def send_sysex(self, data):
        """
        Send arbitrary‑length SysEx payload.    data_bytes: list of integers (0–127)
        """
        # Convert hex string → list[int]        
        if self.idev_out is None:
            return
        if isinstance(data, str):
            data = [int(x, 16) for x in data.split()]
        msg = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x10] + data + [0xF7])
        #print("Sysex value", msg.hex(' '))
        lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
        sleep(0.01)

    def get_note_xy(self, note):
        row = 8 - (note // 10)
        col = (note % 10) - 1
        return col, row

    def get_note_from_xy(self, col, row):
        """Convert col/row to MIDI note number"""
        return 10 * (8 - row) + col + 1

    """
    def _first_status_nibble(self, indata):
        """"""
        Safely return the status nibble (0xF0) as an int, or None on failure.
        Works whether indata is bytes, bytearray, memoryview, or sequence of ints.
        """"""
        try:
            b = bytes(indata)
        except Exception:
            try:
                # last-resort: try to coerce element-wise
                first = indata[0]
                if isinstance(first, int):
                    return first & 0xF0
                if isinstance(first, (bytes, bytearray, memoryview)):
                    return bytes(first)[0] & 0xF0
                return None
            except Exception:
                return None
        if len(b) == 0:
            return None
        return b[0] & 0xF0

    def _should_passthrough(self, indata):
        """"""
        Return True only when:
        - current mode is NOTE
        - event is NOTE ON or NOTE OFF
        """"""
        if self.mode != MODE_NOTE:
            return False
        status = self._first_status_nibble(indata)
        if status is None:
            return False
        return status in (0x90, 0x80)

        
        def midiproc_task(self, jackname):
        
        Diagnostic JACK MIDI processing task.
        No filtering. All events logged.
        Ensures midi_event() receives proper 3-byte tuples.
        

        import jack
        import struct
        from threading import Event

        # First 4 bits of status byte:
        NOTEON = 0x9
        NOTEOFF = 0x8

        client = jack.Client(jackname)
        inport = client.midi_inports.register('in_1')
        outport = client.midi_outports.register('out_1')
        event = Event()

        @client.set_process_callback
        def process(frames):
            outport.clear_buffer()
            if self.filter_enabled.value:
                return
            for offset, indata in inport.incoming_midi_events():

                outport.write_midi_event(offset, indata)  # pass through
                # 3-bytes events
                if len(indata) == 3:
                    status, pitch, vel = struct.unpack('3B', indata)
                    # Note events in MIDI channel 1
                    if status >> 4 in (NOTEON, NOTEOFF) and (status & 0xF) == 0:
                        try:
                            outport.write_midi_event(offset, (status, pitch, vel))
                        except:
                            pass

        @client.set_shutdown_callback
        def shutdown(status, reason):
            print("JACK shutdown:", reason, status)
            event.set()

        with client:
            event.wait()


    def enable_note_filter(self):
        self.filter_enabled.value = 1

    def disable_note_filter(self):
        self.filter_enabled.value = 0 
    """

    def midi_event(self, ev):
        """Handle MIDI input from device"""
        if self.state_manager.power_save_mode:
            return True
        
        evtype = (ev[0] >> 4) & 0x0F
        evchan = ev[0] & 0x0F
        now = monotonic()
        
        # Edge (round buttons) handling (use CC instead of velocity)
        if evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            
            # Mode buttons
            if ccval > 0:
                if ccnum == BTN_SESSION:
                    self._set_layout(MODE_SESSION)
                    if zynthian_gui_config.zyngui.screens["mixer"].launcher_mode:
                        self.state_manager.send_cuia("SCREEN_MIXER")
                    else:
                        self.state_manager.send_cuia("SCREEN_LAUNCHER")
                    return True
                elif ccnum == BTN_NOTE: 
                    self._set_layout(MODE_NOTE) 
                    return True
                elif ccnum == BTN_DEVICE:
                    self._set_layout(MODE_DEVICE) 
                    return True
                elif ccnum == BTN_USER:
                    self._set_layout(MODE_USER)
                    return True
                
                # User mode: fader mode toggle with BTN_SHIFT
                elif self.mode == MODE_USER and ccnum == BTN_SHIFT:
                    modes = ["volume", "pan", "sends"]
                    idx = modes.index(self.fader_mode)
                    self.fader_mode = modes[(idx + 1) % len(modes)]
                    logging.info(f"Fader mode: {self.fader_mode}")
                    faders = self.build_fader_state_from_mixer(self.fader_mode)
                    self.send_fader_init(faders)
                    self.update_fader_leds()
                    print(f"idx = {idx}, self.fader_mode = {self.fader_mode}")
                    if idx == 2:
                        self._feedback.led_on(BTN_VOLUME, self.LEDColors.COLOR_ORANGE)
                    elif idx == 0:
                        self._feedback.led_on(BTN_PAN, self.LEDColors.COLOR_ORANGE)
                    else:
                        self._feedback.led_on(BTN_SENDS, self.LEDColors.COLOR_ORANGE)
                    return True

                # User mode: explicit bottom-row mode selectors (Launchpad Pro only)
                elif self.mode == MODE_USER and ccnum in (BTN_VOLUME, BTN_PAN, BTN_SENDS):
                    selected = {
                        BTN_VOLUME: ("volume", ABLETON_SUB_SELECT_VOLUME_CC),
                        BTN_PAN: ("pan", ABLETON_SUB_SELECT_PAN_CC),
                        BTN_SENDS: ("sends", ABLETON_SUB_SELECT_SENDS_CC),
                    }[ccnum]
                    self.fader_mode, sysex = selected
                    self.send_sysex(sysex)
                    logging.info(f"Fader mode selected: {self.fader_mode}")
                    faders = self.build_fader_state_from_mixer(self.fader_mode)
                    self.send_fader_init(faders)
                    self.update_fader_leds()
                    self.update_mode_leds()
                    self._feedback.led_on(ccnum, self.LEDColors.COLOR_ORANGE)
                    return True
                
                # User mode: fader controls
                elif self.mode == MODE_USER:
                    fader_cc_map = {
                        "volume": FADER_CHANNEL,
                        "pan": FADER_CHANNEL,
                        "sends": FADER_CHANNEL,
                    }
                    if ccnum in fader_cc_map[self.fader_mode]:
                        col = fader_cc_map[self.fader_mode].index(ccnum)
                        if self.fader_mode == "volume":
                            if ccval in VOL_SEND_LEVEL_CC:
                                normalized = VOL_SEND_LEVEL_CC.index(ccval) / 7.0
                            else:
                                normalized = min(127, max(0, ccval)) / 127.0
                            self.set_mixer_param("level", col, normalized)
                            try:
                                self._feedback.led_on(ccnum, VOL_SEND_LEVEL_CC[int(round(normalized * 7))])
                            except Exception as e:
                                logging.error(f"Error occurred while updating VOL_SEND_LEVEL_CC LED: {e}")
                        elif self.fader_mode == "pan":
                            if ccval in PAN_LEVEL_CC:
                                print("Pan mode ccval: ", ccval)
                                idx = PAN_LEVEL_CC.index(ccval)
                                normalized = idx / 7.0 * 2.0 - 1.0
                            else:
                                normalized = ccval / 64.0 - 1.0
                            self.set_mixer_param("balance", col, normalized)
                            self._feedback.led_on(ccnum, PAN_LEVEL_CC[min(7, max(0, int(round((normalized + 1.0) / 2.0 * 7))))])
                        elif self.fader_mode == "sends":
                            if ccval in VOL_SEND_LEVEL_CC:
                                try:
                                    normalized = VOL_SEND_LEVEL_CC.index(ccval) / 7.0    
                                except Exception as e:
                                    logging.error(f"Error occurred while updating VOL_SEND_LEVEL_CC LED: {e}")
                            else:
                                normalized = min(127, max(0, ccval)) / 127.0
                            self.set_mixer_param(f"send_{col}_level", col, normalized)
                            self._feedback.led_on(ccnum, VOL_SEND_LEVEL_CC[int(round(normalized * 7))])
                        return True
                    else:  # Not a fader in USER mode; ignore other buttons                        
                        return True
                
                # Navigation
                elif ccnum == BTN_UP:
                    self.state_manager.send_cuia("ARROW_UP")
                elif ccnum == BTN_DOWN:
                    self.state_manager.send_cuia("ARROW_DOWN")
                elif ccnum == BTN_LEFT:
                    self.state_manager.send_cuia("ARROW_LEFT")
                elif ccnum == BTN_RIGHT:
                    self.state_manager.send_cuia("ARROW_RIGHT")
                else:
                    col, row = self.get_note_xy(ccnum)
                    if col == 8:
                        try:
                            phrase = row + self.scroll_v
                            self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL)
                        except:
                            pass
        
        # Note on handling
        elif evtype == 0x9:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            
            if vel > 0:
                if self.mode == MODE_SESSION:
                    # Launcher grid mode
                    col, row = self.get_note_xy(note)
                    midi_chan = self.get_filtered_midi_chan_by_index(col)
                    if midi_chan is not None:
                        phrase = row + self.scroll_v
                        try:
                            self.zynseq.libseq.togglePlayState(self.zynseq.scene, phrase, midi_chan)
                        except:
                            print("Error toggling play state for phrase {}, channel {}".format(phrase, midi_chan))
                            pass
                    return True
                
                elif self.mode == MODE_NOTE:
                    pos = self.scroll_h + note % 8
                    row = note // 8
                    midi_chan = self.get_filtered_midi_chan_by_index(pos)
                    try:
                        active_chain = self.chain_manager.active_chain.chain_id
                        midi_out = active_chain.midi_out
                        midi_chan = self.get_filtered_midi_chan_by_index(pos)
                        print("NOTE MODE:", midi_out, midi_chan, note, vel)
                        if midi_chan is not None:
                            lib_zyncore.dev_send_note_on(self.idev_out, midi_chan, note, vel)
                            #self.last_press = (note, midi_chan, midi_out)
                    except Exception as e:
                        print("Note mode error:", e)
                    print("OUT:", active_chain.midi_out,
                        "CHAN:", active_chain.midi_chan,
                        "NOTE:", note)
                    print("NOTE MODE HIT", note, vel)
                    print("RAW:", ev)
                    return True
                
                elif self.mode == MODE_DEVICE:
                    # Device control mode - route to DeviceHandler
                    col, row = self.get_note_xy(note)
                    logging.debug(f"Pro MK2: Received device mode note: 0x{note:02X} at col={col}, row={row}")
                    try:
                        self._device_handler.note_on(note, vel)
                    except Exception:
                        logging.exception("DeviceHandler.note_on failed")
                    return True
        
        # Note off handling
        elif evtype == 0x8:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            
            if self.mode == MODE_NOTE and self.last_press:
                try:
                    last_note, midi_chan, midi_out = self.last_press
                    if last_note == note:
                        lib_zyncore.dev_send_note_off(midi_out, midi_chan, note, vel)
                        self.last_press = None
                except:
                    pass
            # forward note_off to device handler in device mode as well
            if self.mode == MODE_DEVICE:
                try:
                    self._device_handler.note_off(note)
                except Exception:
                    logging.exception("DeviceHandler.note_off failed")
            return True
        
        # SysEx
        elif ev[0] == 0xF0:
            logging.info(f"Received SysEx => {ev.hex(' ')}")
            return True
        
        return False

    def sleep_on(self):
        """Put device in sleep mode"""
        self.send_sysex("09 00")

    def sleep_off(self):
        """Wake device from sleep mode"""
        self.send_sysex("09 01")

    def init(self):
        self.sleep_off() # Wake device
        sleep(0.05)  # Give device time to wake
        self.send_sysex(MODE_SELECT_ABLETON_CC) # Enter Ableton mode session mode
        sleep(0.05)
        self.send_sysex(ABLETON_SUB_SELECT_SESSION_CC) # Select session layout (layout session = 0x00)
        sleep(0.05)
        self.mode = MODE_SESSION # MODE_SESSION
        # Ensure hardware LEDs are consistent via FeedbackLEDs
        try:
            self._feedback.all_off()
        except Exception:
            pass
        self.update_mode_leds()
        self.refresh_pads()
        self.update_navigation_leds()
        super().init()
        zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_gui_show_screen)
        # Route GUI/media events to DeviceHandler for LED feedback (best-effort)
        try:
            zynsigman.register_queued(zynsigman.S_MEDIA, zynsigman.SS_MEDIA_PLAYER_STATE, self._device_handler.on_media_change)
            zynsigman.register_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self._device_handler.on_screen_change)
        except Exception:
            pass

    def end(self):
        super().end()
        zynsigman.unregister(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_SCREEN, self.on_gui_show_screen)
        self._feedback.all_off()
        self.send_sysex(MODE_SELECT_STANDALONE_CC) # Exit DAW session mode
        self.send_sysex(STANDALONE_SUB_SELECT_NOTE_CC) # Select Notes/Drum layout, page 0

    def send_fader_init(self, faders):
        """
        Send Launchpad Pro MK2 fader/pan initialisation SysEx.
        faders = list of tuples: (index, fader_type, colour, value)
        index: 0–7 | fader_type: 0 = fader, 1 = pan | colour: 1–127 (0 is LED off, so minimum is 1) | value: 0–127
        """
        if self.idev_out is None:
            return
        fader_params = [0x2B] 
        for (index, fader_type, colour, value) in faders:
            colour = zynthian_gui_config.LAUNCHER_COLOUR[index]["launchpad"]
            if colour < 1:
                colour = 1
            else:
                pass
            fader_params += [
                index,
                fader_type,
                colour,
                value
            ]
        self.send_sysex(fader_params)

    def build_fader_state_from_mixer(self, mode):
        faders = []
        for ch in range(8):
            if mode == "volume":
                val = int(self.get_mixer_param("level", ch) * 127.0)
                ftype = 0
            elif mode == "pan":
                val = int((self.get_mixer_param("balance", ch) + 1.0) * 63.5)
                ftype = 1
            else:  # sends mode
                val = 0
                try:
                    chain = self.chain_manager.get_filtered_chain_by_index(ch)
                    if chain and chain.zynmixer_proc:
                        mixer_chan = chain.mixer_chan
                        val = int(chain.zynmixer_proc.zynmixer.get_send_level(mixer_chan, 0) * 127)
                except (IndexError, AttributeError):
                    pass
                ftype = 0
            faders.append((ch, ftype, 0, val)) # Launchpad manual: initial colour should be 0 (off) for compatibility
        return faders

    def _set_layout(self, mode: int):
        """Sets hardware layout based on mode using mapping."""
        layout_map = {
            MODE_SESSION: (MODE_SELECT_ABLETON_CC, ABLETON_SUB_SELECT_SESSION_CC),
            MODE_NOTE: (MODE_SELECT_ABLETON_CC, ABLETON_SUB_SELECT_CHROMATIC_CC),
            MODE_DEVICE: (MODE_SELECT_ABLETON_CC, ABLETON_SUB_SELECT_SESSION_CC),  # Could use standalone if preferred
            MODE_USER: (MODE_SELECT_ABLETON_CC, ABLETON_SUB_SELECT_VOLUME_CC)
        }
        
        cc_cmd, sub_cc = layout_map.get(mode)
        if not (cc_cmd and sub_cc):
            logging.error(f"Unknown mode {mode}")
            return False

        print("Current layout: ", layout_map, mode, self.mode)

        self.send_sysex(cc_cmd)
        sleep(0.05)
        self.send_sysex(sub_cc)
        self.mode = mode
        if mode == MODE_SESSION:
            self._feedback.all_off()
            self.refresh_pads()
        elif mode == MODE_NOTE:
            pass
        elif mode == MODE_DEVICE:
            self._device_handler.refresh()
        elif mode == MODE_USER:
            faders = self.build_fader_state_from_mixer(self.fader_mode) # Build fader values from mixer
            self.send_fader_init(faders)
            self.update_fader_leds()
            self._feedback.led_on(BTN_VOLUME, self.LEDColors.COLOR_ORANGE)
            self._feedback.led_on(BTN_SHIFT, self.LEDColors.COLOR_BLUE)
        self.update_mode_leds()
        self.update_navigation_leds()

    def refresh_pads(self):
        """Refresh all grid pads and launcher column in session mode"""
        try:
            # Refresh grid pads (columns 0-7)
            for row in range(self.rows):
                for col in range(self.cols):
                    phrase = row + self.scroll_v
                    try:
                        # Convert column to MIDI channel (same as midi_event)
                        midi_chan = self.get_filtered_midi_chan_by_index(col)
                        if midi_chan is not None:
                            pad_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][midi_chan]
                            self.update_pad(row, col, pad_info)
                    except (KeyError, IndexError, TypeError):
                        # Pad doesn't exist or is empty, skip it
                        pass           
            # Refresh launcher column (rightmost column)
            for row in range(self.rows):
                phrase = row + self.scroll_v
                try:
                    pad_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]
                    pad_info["empty"] = False
                    col = self.phrase_launcher_col
                    self.update_pad(row, col, pad_info)
                except (KeyError, IndexError, TypeError): # Phrase doesn't exist or is empty, skip it                    
                    pass
        except Exception as e:
            logging.error(f"Error refreshing pads: {e}", exc_info=True)

    def update_mode_leds(self):
        """Update LED indicators for active mode"""
        try:
            for btn in (BTN_SESSION, BTN_NOTE, BTN_DEVICE, BTN_USER):
                self._feedback.led_off(btn)
            color = self.LEDColors.MODE_COLOUR
            if self.mode == MODE_SESSION:
                self._feedback.led_on(BTN_SESSION, self.LEDColors.COLOR_BLUE)
            elif self.mode == MODE_NOTE:
                self._feedback.led_on(BTN_NOTE, self.LEDColors.COLOR_ORANGE)
            elif self.mode == MODE_DEVICE:
                self._feedback.led_on(BTN_DEVICE, self.LEDColors.COLOR_WHITE)
            elif self.mode == MODE_USER:
                self._feedback.led_on(BTN_USER, color)
            return
        except Exception as e:
            logging.error(f"Error updating mode LEDs: {e}", exc_info=True)

    def update_navigation_leds(self):
        """Light navigation arrows top left"""
        for btn in (BTN_UP, BTN_DOWN):
            self._feedback.led_on(btn, self.LEDColors.COLOR_DARK_BLUE)
        for btn in (BTN_LEFT, BTN_RIGHT):
            self._feedback.led_on(btn, self.LEDColors.COLOR_DARK_GREEN)

    def on_wsled_state_change(self):
        if self.mode == MODE_DEVICE:
            self._device_handler.refresh()

    def update_fader_leds(self):
        for btn in (BTN_VOLUME, BTN_PAN, BTN_SENDS):
            self._feedback.led_on(btn, self.LEDColors.COLOR_BLUE)

    def _get_fader_cc_map(self):
        return {
            "volume": FADER_CHANNEL,
            "pan": FADER_CHANNEL,
            "sends": FADER_CHANNEL,
        }

    def _get_fader_level_value(self, mode, value):
        if value is None:
            return 0
        try:
            if mode == "volume" or mode == "sends":
                idx = int(round(min(1.0, max(0.0, value)) * 7))
                return VOL_SEND_LEVEL_CC[idx]
            elif mode == "pan":
                idx = int(round(min(1.0, max(-1.0, value)) * 0.5 * 7 + 3.5))
                idx = min(7, max(0, idx))
                return PAN_LEVEL_CC[idx]
        except Exception:
            pass
        return self.LEDColors.COLOR_YELLOW

    def update_mixer_strip(self, chan, symbol, value, mixbus=False):
        if self.idev_out is None or mixbus:
            return
        try:
            pos = self.chain_manager.get_pos_by_mixer_chan(chan, mixbus)
            if pos is None or pos < 0 or pos >= len(self._get_fader_cc_map()["volume"]):
                return
            if symbol == "level":
                led_column = FADER_CHANNEL[pos]
                color = self._get_fader_level_value("volume", value)
                self._send_fader_init(led_column, color, 0, value)
            elif symbol == "balance":
                led_column = FADER_CHANNEL[pos]
                color = self._get_fader_level_value("pan", value)
                self._send_fader_init(led_column, color, 1, value)
            elif symbol.startswith("send_") and symbol.endswith("_level"):
                led_column = FADER_CHANNEL[pos]
                color = self._get_fader_level_value("sends", value)
                self._send_fader_init(led_column, color, 0, value)
        except Exception:
            pass
    
    def on_gui_show_screen(self, screen):
         """Sync mode with GUI screen"""
         if screen == "launcher":
             pass

    def update_pad(self, row, col, pad_info):
        """Updates pad LEDs in session mode"""
        if self.mode != MODE_SESSION:
            return
        chan = 0
        color = 0 # AKA velocity
        note = 10 * (8 - row) + col + 1
        try:
            state = pad_info["state"]
            mode = pad_info["mode"]
            repeat = pad_info["repeat"]
            if col == self.cols:
                group = 0
            else:
                group = pad_info["group"]
            if repeat == 0 or mode == 0 or group >= MAX_NUM_MIDI_CHANS:
                pass
            elif state == zynseq.SEQ_STOPPED:
                chan = 0
                vel = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
            elif state == zynseq.SEQ_PLAYING:
                chan = 2
                vel = zynthian_gui_config.LAUNCHER_COLOUR[group]["launchpad"]
            elif state == zynseq.SEQ_STOPPING:
                chan = 1
                vel = zynthian_gui_config.LAUNCHER_STOPPING_COLOUR["launchpad"]
            elif state == zynseq.SEQ_STARTING:
                chan = 1
                vel = zynthian_gui_config.LAUNCHER_STARTING_COLOUR["launchpad"]
        except:
            pass
        lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)

class   FeedbackLEDs:
    def __init__(self, idev):
        self._idev = idev
        self._state = {}
        self._timer = RunTimer()

    def all_off(self):
        self.control_leds_off()
        self.pad_leds_off()

    def control_leds_off(self):
        buttons = [
            BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_VOLUME,
            BTN_PAN, BTN_SENDS, BTN_DEVICE, BTN_MUTE, BTN_SOLO,
            BTN_RECORD_ARM, BTN_SHIFT, BTN_CLICK,
            BTN_UNDO, BTN_DELETE, BTN_QUANTISE, BTN_DUPLICATE, BTN_DOUBLE,
            BTN_RECORD, BTN_RECORD_ARM, BTN_TRACK_SELECT, BTN_STOP_CLIP, 
            BTN_PLAY_ROW_1, BTN_PLAY_ROW_2, BTN_PLAY_ROW_3, BTN_PLAY_ROW_4,
            BTN_PLAY_ROW_5, BTN_PLAY_ROW_6, BTN_PLAY_ROW_7, BTN_PLAY_ROW_8  
        ]
        for btn in buttons:
            self.led_off(btn)

    def pad_leds_off(self):
        for btn in BTN_PAD_RANGE:
            self.led_off(btn)

    def led_state(self, led, state): # Turns led on if off and vice versa?
        (self.led_on if state else self.led_off)(led)

    def led_off(self, led, overlay=False): # send note with channel=0, velocity=0 to turn LED off
        self._timer.remove(led)
        lib_zyncore.dev_send_note_on(self._idev, 0, led, 0)
        if not overlay:
            self._state[led] = (0, 0)                                                                                                                         

    def led_on(self, led, color=1, channel=0, overlay=False):
        """Turn LED on. `color` maps to velocity/colour and `channel` can select mode."""
        self._timer.remove(led)
        if led in BTN_PAD_RANGE:
            lib_zyncore.dev_send_note_on(self._idev, channel, led, color)
        else:
            lib_zyncore.dev_send_ccontrol_change(self._idev, channel, led, color)
        if not overlay:
            self._state[led] = (color, channel)

    def led_flash(self, led): # use channel=1 and velocity=2 for blink/pulse behaviour
        self._timer.remove(led)
        lib_zyncore.dev_send_note_on(self._idev, 1, led, 2)

    def remove_overlay(self, led):
        old_state = self._state.get(led)
        if old_state:
            color, channel = old_state
            self.led_on(led, color, channel)
        else:
            self._timer.remove(led)
            lib_zyncore.dev_send_note_on(self._idev, 0, led, 0)

    def delayed(self, action, timeout, led, *args, **kwargs):
        action = getattr(self, action)
        self._timer.add(led, timeout, action, *args, **kwargs)

    def clear_delayed(self, led):
        self._timer.remove(led)
    
class DeviceHandler(ModeHandlerBase):
    ledcolours = zynthian_ctrldev_launchpad_pro_mk2.LEDColors()
    WSCOLORS_DICT = ZYNSWITCH_SCREEN_COLORS = {
        "0": ledcolours.COLOR_DARK_BLUE,
        "G": ledcolours.COLOR_DARK_GREEN,
        "R": ledcolours.COLOR_RED,
        "O": ledcolours.COLOR_DARK_ORANGE,
        "Y": ledcolours.COLOR_YELLOW,
        "P": ledcolours.COLOR_ALT_ON,
        "T": ledcolours.COLOR_LIGHT_BLUE,
        "B": ledcolours.COLOR_DEEP_BLUE,
    }
    
    ZYNSWITCH_NOTE = {
        4:    BTN_OPT_ADMIN,
        5:    BTN_MIX_LEVEL,
        6:    BTN_CTRL_PRESET,
        7:    BTN_ZS3_SHOT,

        8:    BTN_ALT,
        9:    BTN_PAD_STEP,
        10:   BTN_METRONOME,
        11:   BTN_F1,

        12:    BTN_PAD_RECORD,
        13:    BTN_PAD_STOP,
        14:    BTN_PAD_PLAY,
        15:    BTN_F2,

        16:    BTN_BACK_NO,
        17:    BTN_PAD_UP,
        18:    BTN_SEL_YES,
        19:    BTN_F3,

        20:    BTN_PAD_LEFT,
        21:    BTN_PAD_DOWN,
        22:    BTN_PAD_RIGHT,
        23:    BTN_F4,

        24:    BTN_PAD_ZYNPOT_SWITCH_1,
        25:    BTN_PAD_ZYNPOT_SWITCH_2,
        26:    BTN_PAD_ZYNPOT_SWITCH_3,
        27:    BTN_PAD_ZYNPOT_SWITCH_4,
    }

    ZYNSWITCH_NOTES_AND_COLORS = {
        4: (BTN_OPT_ADMIN, ZYNSWITCH_SCREEN_COLORS),
        5: (BTN_MIX_LEVEL, ZYNSWITCH_SCREEN_COLORS),
        6: (BTN_CTRL_PRESET, ZYNSWITCH_SCREEN_COLORS),
        7: (BTN_ZS3_SHOT, ZYNSWITCH_SCREEN_COLORS),

        8: (BTN_ALT, ZYNSWITCH_SCREEN_COLORS),
        9: (BTN_METRONOME, ZYNSWITCH_SCREEN_COLORS),
        10: (BTN_PAD_STEP, ZYNSWITCH_SCREEN_COLORS),
        11: (BTN_F1, WSCOLORS_DICT),

        12: (BTN_PAD_RECORD, WSCOLORS_DICT),
        13: (BTN_PAD_STOP, WSCOLORS_DICT),
        14: (BTN_PAD_PLAY, WSCOLORS_DICT),
        15: (BTN_F2, WSCOLORS_DICT),

        16: (BTN_F3, WSCOLORS_DICT),
        17: (BTN_SEL_YES, WSCOLORS_DICT),
        18: (BTN_PAD_UP, WSCOLORS_DICT),
        19: (BTN_BACK_NO, WSCOLORS_DICT),
        
        20: (BTN_PAD_LEFT, WSCOLORS_DICT),
        21: (BTN_PAD_DOWN, WSCOLORS_DICT),
        22: (BTN_PAD_RIGHT, WSCOLORS_DICT),
        23: (BTN_F4, WSCOLORS_DICT),
    }

    def __init__(self, state_manager, leds, colors):
        super().__init__(state_manager)
        self._leds = leds
        self._colors = colors
        self._btn_timer = ButtonTimer(self._handle_timed_button)
        self.cuia_queue = state_manager.cuia_queue

    def refresh(self):
        self._leds.all_off()

        if zynthian_gui_config.zyngui is None:
            return
        wsleds = zynthian_gui_config.zyngui.wsleds
        if wsleds is None:
            return

        try:
            for index, color_name in enumerate(
                    wsleds.last_wsled_state.split(","), start=4):
                note, colors = self.ZYNSWITCH_NOTES_AND_COLORS.get(
                    index, (None, self.WSCOLORS_DICT))
                if note is None:
                    continue
                color = colors.get(color_name, 0)
                if color:
                    self._leds.led_on(note, color) #, LED_ON
                    print("Note, Colour and LED_ON value is: ", note, " ", color) #, " ", LED_ON
                else:
                    self._leds.led_off(note)
        except Exception:
            logging.exception("Launchpad device LED refresh failed")

    def on_screen_change(self, screen):
        super().on_screen_change(screen)
        self.refresh()

    def on_media_change(self, media, kind, state):
        self.refresh()

    def note_on(self, note, velocity, shifted_override=None):
        self._on_shifted_override(shifted_override)

        index = next(
            (index for index, mapped_note in self.ZYNSWITCH_NOTE.items()
             if mapped_note == note),
            None,
        )
        if index is not None:
            self.cuia_queue.put_nowait(("zynswitch", (index, "P")))
            self._btn_timer.is_pressed(note, time.time())
            return True

        return False

    def note_off(self, note, shifted_override=None):
        self._on_shifted_override(shifted_override)
        self._btn_timer.is_released(note)
        self.refresh()
        return True

    def _handle_timed_button(self, note, press_type):
        index = next(
            (index for index, mapped_note in self.ZYNSWITCH_NOTE.items()
             if mapped_note == note),
            None,
        )
        if index is not None:
            self.cuia_queue.put_nowait(
                ("zynswitch", (index, PRESSTYPE_DICT.get(press_type, "S")))
            )
            return True

        return False