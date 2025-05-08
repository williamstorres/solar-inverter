#!/usr/bin/python

from os.path import exists
import pickle
import sys
from datetime import datetime
import time
import serial
import json
from crcmod import mkCrcFun
from paho.mqtt import client as mqtt_client


def settings_exist(settingsFileName):
    if exists(settingsFileName):
        return 1
    else:
        if exists("../" + settingsFileName):
            return 2
        else:
            return 0

def generate_settings_file(settingsFileName, folder_level, settings_content):
    settings_json = json.dumps(settings_content)
    if folder_level == 1:
        settings_file = open(settingsFileName,"w")
    else:
        settings_file = open("../" + settingsFileName,"w")
    settings_file.write(settings_json)
    settings_file.close()

def read_settings_file(settingsFileName, folder_level):
    if folder_level == 1:
        settings_file = open(settingsFileName, "rb")
    else:
        settings_file = open("../" + settingsFileName, "rb")
    settings_content = json.load(settings_file)
    settings_file.close()
    return settings_content

def write_settings_file(settingsFileName, folder_level, settingsContent):
    settings_json = json.dumps(settingsContent)
    if folder_level == 1:
        settings_file = open(settingsFileName,"w")
    else:
        settings_file = open("../" + settingsFileName,"w")
    settings_file.write(settings_json)
    settings_file.close()
    return 0

def connect_inverter(settings):
    ser = serial.Serial(port=settings["port"], baudrate=settings["baudrate"], timeout=settings["timeout"])
    return ser

def disconnect_inverter(inverter):
    inverter.close()
    
def write_inverter(inverter, data):
    inverter.write(data)
    
def read_inverter_to_string(inverter, cut_length=3):
    bResponse = inverter.read_until(b"\x0D", size=128)
    sResponse = bResponse[0:len(bResponse)-cut_length].decode()
    return sResponse

def crc16_xmodem(data):
    crc16 = mkCrcFun(0x11021, rev=False, initCrc=0x0000, xorOut=0x0000)
    return crc16(data)

def init_inverter():
    settingsFileName = "settings.ini"
    RS232_settings = {"port": "/dev/ttyUSB0", "baudrate": 2400, "timeout": 5}

    settingsFileFolderLevel = settings_exist(settingsFileName)
    if settingsFileFolderLevel == 0:
        generate_settings_file(settingsFileName, 1, RS232_settings)
        settingsFileFolderLevel = 1
    
    readSettingsContent = read_settings_file(settingsFileName, settingsFileFolderLevel)

    for x in RS232_settings:
        if x not in readSettingsContent:
            readSettingsContent[x] = RS232_settings[x]
            write_settings_file(settingsFileName, settingsFileFolderLevel, readSettingsContent)
    
    return read_settings_file(settingsFileName, settingsFileFolderLevel)

def get_inverter():
    inverter = connect_inverter(settings=init_inverter())
    inverter.reset_input_buffer()
    inverter.reset_output_buffer()
    inverter.flush()
    return inverter;

def get_charging_status(device_status):
    if device_status[5:8] == "000":
        return "do nothing"
    if device_status[5:8] == "110":
        return "Charging on with SCC charge on"
    if device_status[5:8] == "101":
        return "Charging on with AC charge on"
    if device_status[5:8] == "111":
        return "Charging on with SCC and AC charge on"
    return device_status[5:8]

def INQ_device_general_status_parameters(inverter):
    command = "QPIGS"
    command_bytes = command.encode("utf-8")
    command_crc = crc16_xmodem(command_bytes)
    command_bytes_array = bytearray(command_bytes)
    command_bytes_array.append(command_crc >> 8)
    command_bytes_array.append(command_crc & 255)
    command_bytes_array.append(13)
    write_inverter(inverter, command_bytes_array)
    response = read_inverter_to_string(inverter)
    
    grid_voltage = response[1:6]
    grid_frequency = response[7:11]
    ac_output_voltage = response[12:17]
    ac_output_frequency = response[18:22]
    ac_output_apparent_power = response[23:27]
    ac_output_active_power = response[28:32]
    output_load_percent = response[33:36]
    bus_voltage = response[37:40]
    battery_voltage = response[41:46]
    battery_charging_current = response[47:50]
    battery_capacity = response[51:54]
    inverter_heat_sink_temp = response[55:59]
    pv1_input_current = response[60:64]
    pv1_input_voltage = response[65:70]
    battery_voltage_from_scc = response[71:76]
    battery_discharge_current = response[77:82]
    device_status = response[83:91]
    add_sbu_priority_version = device_status[0]
    configuration_status = device_status[1]
    scc_firmware_version = device_status[2]
    load_status = device_status[3]
    battery_voltage_to_steady_while_charging = device_status[4]
    #print(device_status[5:8])
    if device_status[5:8] == "000":
        charging_status = "do nothing"
    if device_status[5:8] == "110":
        charging_status = "Charging on with SCC charge on"
    if device_status[5:8] == "101":
        charging_status = "Charging on with AC charge on"
    if device_status[5:8] == "111":
        charging_status = "Charging on with SCC and AC charge on"
    battery_voltage_offset_for_fans_on = response[92:94]
    eeprom_version = response[95:97]
    pv1_charging_power = response[98:103]
    device_status_2 = response[104:107]
    charging_to_floating_mode = device_status_2[0]
    switch_on = device_status_2[1]
    dustproof_installed = device_status_2[2]

    return {
        "grid_voltage": grid_voltage,
        "grid_frequency": grid_frequency,
        "ac_output_voltage": ac_output_voltage,
        "ac_output_frequency": ac_output_frequency,
        "ac_output_apparent_power": ac_output_apparent_power,
        "ac_output_active_power": ac_output_active_power,
        "output_load_percent": output_load_percent,
        "bus_voltage": bus_voltage,
        "battery_voltage": battery_voltage,
        "battery_charging_current": battery_charging_current,
        "battery_capacity": battery_capacity,
        "inverter_heat_sink_temp": inverter_heat_sink_temp,
        "pv1_input_current": pv1_input_current,
        "pv1_input_voltage": pv1_input_voltage,
        "battery_voltage_from_scc": battery_voltage_from_scc,
        "device_status": device_status,
        "load_status": load_status,
        "battery_voltage_offset_for_fans_on": battery_voltage_offset_for_fans_on,
        "pv1_charging_power": pv1_charging_power,
        "charging_to_floating_mode": charging_to_floating_mode
    }    

def send_to_mqtt(parameters):
    topic = "inverter"
    client_id = f'raspberry-inverter-1'
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, client_id)
    client.username_pw_set("will", "12345678")
    client.connect('localhost', 1883)
    client.publish(topic, payload=str(parameters), qos=1)

if __name__ == "__main__":
    inverter = get_inverter()
    print(INQ_device_general_status_parameters(inverter))
    # send_to_mqtt(INQ_device_general_status_parameters_dummy())
    disconnect_inverter(inverter)
