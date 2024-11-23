# sim7080_driver.py
import machine
import utime
import json
from machine import Pin

# Global variables
uart_port = 0
uart_baudrate = 115200
Pico_SIM7080G = machine.UART(uart_port, uart_baudrate)

def send_at(cmd, back="OK", timeout=1500):
    rec_buff = b''
    Pico_SIM7080G.write((cmd + '\r\n').encode())
    prvmills = utime.ticks_ms()
    while (utime.ticks_ms() - prvmills) < timeout:
        if Pico_SIM7080G.any():
            rec_buff = b"".join([rec_buff, Pico_SIM7080G.read(1)])
    if rec_buff!= '':
        if back not in rec_buff.decode():
            if 'ERROR' in rec_buff.decode():
                print(cmd + 'back:\t' + rec_buff.decode())
                return 0
            else:
                rec_buff = b''
                rec_buff = send_at_wait_resp(cmd, back, timeout)
                if back not in rec_buff.decode():
                    print(cmd + 'back:\t' + rec_buff.decode())
                    return 0
                else:
                    return 1
        else:
            print(rec_buff.decode())
            return 1
    else:
        print(cmd + 'no response\n')
        rec_buff = send_at_wait_resp(cmd, back, timeout)
        if back not in rec_buff.decode():
            print(cmd + 'back:\t' + rec_buff.decode())
            return 0
        else:
            return 1

def send_at_wait_resp(cmd, back, timeout=2000):
    rec_buff = b''
    Pico_SIM7080G.write((cmd + '\r\n').encode())
    prvmills = utime.ticks_ms()
    while (utime.ticks_ms() - prvmills) < timeout:
        if Pico_SIM7080G.any():
            rec_buff = b"".join([rec_buff, Pico_SIM7080G.read(1)])
    if rec_buff!= '':
        if back not in rec_buff.decode():
            print(cmd + 'back:\t' + rec_buff.decode())
        else:
            print(rec_buff.decode())
    else:
        print(cmd + 'no response')
    return rec_buff

def check_start():
    send_at("AT", "OK")
    utime.sleep(1)
    for i in range(1, 4):
        if send_at("AT", "OK") == 1:
            print('------SIM7080G is ready------\r\n')
            send_at("ATE1", "OK")
            break
        else:
            module_power()
            print('------SIM7080G is starting up, please wait------\r\n')
            utime.sleep(5)

def module_power():
    pwr_key = machine.Pin(14, machine.Pin.OUT)
    pwr_key.value(1)
    utime.sleep(2)
    pwr_key.value(0)

def set_network():
    print("Setting to NB-IoT mode:\n")
    send_at("AT+CFUN=0", "OK")
    send_at("AT+CNMP=38", "OK")  # Select LTE mode
    send_at("AT+CMNB=1", "OK")  # Select NB-IoT mode
    send_at("AT+CFUN=1", "OK")
    send_at("AT+CGDCONT=1,\"IPV4V6\",\"super\"")
    send_at("AT+CBANDCFG?")

def check_network():
    if send_at("AT+CPIN?", "READY")!= 1:
        print("------Please check whether the sim card has been inserted------\n")
    for i in range(1, 10):
        if send_at("AT+CGATT?", "1"):
            print('------SIM7080G is online------\r\n')
            break
        else:
            print('------SIM7080G is offline, please wait...------\r\n')
            utime.sleep(5)
            continue
    send_at("AT+CSQ", "OK")
    send_at("AT+CPSI?", "OK")
    send_at("AT+COPS?", "OK")
    get_resp_info = str(send_at_wait_resp("AT+CGNAPN", "OK"))
    getapn1 = get_resp_info[get_resp_info.find('\"') + 1:get_resp_info.rfind('\"')]
    send_at("AT+CNCFG=0,1,\"" + getapn1 + "\"", "OK")
    if send_at('AT+CNACT=0,1', 'ACTIVE'):
        print("Network activation is successful\n")
    else:
        print("Please check the network and try again!\n")

def set_http_length(body_length):
    send_at(f'AT+SHCONF="BODYLEN",{body_length}', 'OK')
    send_at('AT+SHCONF="HEADERLEN",350', 'OK')

def set_http_content():
    send_at('AT+SHCHEAD', 'OK')
    send_at('AT+SHAHEAD="Content-Type","application/json"', 'OK')
    send_at('AT+SHAHEAD="Cache-control","no-cache"', 'OK')
    send_at('AT+SHAHEAD="Connection","keep-alive"', 'OK')
    send_at('AT+SHAHEAD="Accept","*/*"', 'OK')

def http_get(server_url, server_path):
    send_at('AT+SHDISC', 'OK')
    send_at('AT+SHCONF="URL","' + server_url + '"', 'OK')
    set_http_length(len(server_path.encode('utf-8')))
    send_at('AT+SHCONN', 'OK', 3000)
    send_at('AT+SHSTATE?')
    if send_at('AT+SHSTATE?', '1'):
        set_http_content()
        resp = str(send_at_wait_resp('AT+SHREQ="' + server_path + '",1', 'OK', 8000))
        try:
            get_pack_len = int(resp[resp.rfind(',') + 1:-5])
            if get_pack_len > 0:
                response_body = send_at_wait_resp('AT+SHREAD=0,' + str(get_pack_len), 'OK', 5000)
                print("Response body:", response_body)
           #     send_at_wait_resp('AT+SHREAD=0,' + str(get_pack_len), 'OK', 5000)
                send_at('AT+SHDISC', 'OK')
                return response_body  # Return the decoded response body
            else:
                print("HTTP Get failed!\n")
                return "error"
        except ValueError:
            print("ValueError!\n")
            return None
    else:
        print("HTTP connection disconnected, please check and try again\n")
        return None

def http_post(server_url, server_path, post_data):
    print("Disconnecting any existing HTTP connection...")
    send_at('AT+SHDISC', 'OK')
    print("Setting the URL...")
    send_at('AT+SHCONF="URL","' + server_url + '"', 'OK')
    print("Setting the HTTP body length...")
    set_http_length(len(post_data.encode('utf-8')))
    send_at('AT+SHSTATE?')

    print("Establishing a connection...")
    send_at('AT+SHCONN', 'OK', 5000)
    if send_at('AT+SHSTATE?', '1'):
        print("Setting the HTTP headers...")
        set_http_content()
        body_length = len(post_data.encode('utf-8'))
        print(f"Preparing to send the body with length: {body_length}...")
        send_at(f'AT+SHBOD={body_length},10000', '>')
        print("Sending the JSON data...")
        send_at(post_data, 'OK')
        resp = str(send_at_wait_resp('AT+SHREQ="' + server_path + '",3', 'OK', 8000))
        print(f"Response received: {resp}")

        try:
            get_pack_len = int(resp[resp.rfind(',') + 1:-5])
            if get_pack_len > 0:
                print(f"Reading response data of length: {get_pack_len}...")
                send_at_wait_resp('AT+SHREAD=0,' + str(get_pack_len), 'OK', 3000)
                print("Disconnecting after sending the request...")
                send_at('AT+SHDISC', 'OK')
                return 'OK'
            else:
                print("HTTP Post failed!\n")
                return 'Error'
        except ValueError:
            print("Failed to extract packet length from response:", resp)
    else:
        print("HTTP connection disconnected, please check and try again\n")

