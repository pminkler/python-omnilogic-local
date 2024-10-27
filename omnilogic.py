import asyncio
import xml.etree.ElementTree as ET
from flask import Flask, jsonify, request
from pyomnilogic_local.api import OmniLogicAPI
from pyomnilogic_local.types import MessageType

# Initialize Flask app
app = Flask(__name__)

# Initialize the global event loop and OmniLogicAPI instance
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
omnilogic_api = None

async def initialize_omnilogic_api():
    global omnilogic_api
    omnilogic_api = OmniLogicAPI("192.168.1.85", 10444, 5.0)  # Replace with your actual OmniLogic IP and port

# Utility function to run async calls using the pre-initialized `loop`
def run_async(func, *args):
    return loop.run_until_complete(func(*args))

# Helper function to serialize complex objects
def serialize(obj, depth=3):
    if depth <= 0:
        return str(obj)  # Stop recursion
    if hasattr(obj, '__dict__'):
        return {k: serialize(v, depth - 1) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [serialize(item, depth - 1) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize(v, depth - 1) for k, v in obj.items()}
    else:
        return obj

# Endpoint to set heater temperature (for pool or spa)
@app.route('/set_heater_temp', methods=['POST'])
def set_heater_temp():
    data = request.get_json()
    body_of_water = data.get('body_of_water', 'pool')  # 'pool' or 'spa'
    temperature = data.get('temperature')

    heater_id = 5 if body_of_water == 'pool' else 13 if body_of_water == 'spa' else None
    if heater_id is None:
        return jsonify({"error": "Invalid body of water. Use 'pool' or 'spa'."}), 400

    run_async(omnilogic_api.async_set_heater_enable, heater_id, True)
    run_async(omnilogic_api.async_set_heater, heater_id, temperature, "F")
    return jsonify({"status": "success", "message": f"{body_of_water.capitalize()} heater set to {temperature}°F"})

# Endpoint to control filter pump speed (for pool or spa)
@app.route('/set_filter_pump_speed', methods=['POST'])
def set_filter_pump_speed():
    data = request.get_json()
    body_of_water = data.get('body_of_water', 'pool')
    speed = data.get('speed')

    pool_id = 1 if body_of_water == 'pool' else 2
    equipment_id = 3 if body_of_water == 'pool' else 11 if body_of_water == 'spa' else None
    if equipment_id is None:
        return jsonify({"error": "Invalid body of water. Use 'pool' or 'spa'."}), 400

    run_async(omnilogic_api.async_set_filter_speed, pool_id, equipment_id, speed)
    return jsonify({"status": "success", "message": f"{body_of_water.capitalize()} filter pump set to {speed}%"})

# Endpoint to control relays (e.g., waterfall, blower)
@app.route('/set_relay', methods=['POST'])
def set_relay():
    data = request.get_json()
    relay_name = data.get('relay_name')
    state = data.get('state', 'off').lower()

    relay_id = 29 if relay_name == 'waterfall' else 16 if relay_name == 'blower' else None
    if relay_id is None:
        return jsonify({"error": "Invalid relay name. Use 'waterfall' or 'blower'."}), 400

    run_async(omnilogic_api.async_set_equipment, relay_id, state == 'on')
    return jsonify({"status": "success", "message": f"{relay_name.capitalize()} turned {state}"})

# Endpoint to dump all configuration data
@app.route('/dump_config', methods=['GET'])
def dump_config():
    try:
        config = run_async(omnilogic_api.async_get_config)
        return jsonify({"config": serialize(config)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to dump all telemetry data
@app.route('/dump_telemetry', methods=['GET'])
def dump_telemetry():
    try:
        telemetry = run_async(omnilogic_api.async_get_telemetry)
        return jsonify({"telemetry": serialize(telemetry)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trigger_theme', methods=['POST'])
def trigger_theme():
    data = request.get_json()
    group_id = data.get('group_id')
    start = data.get('start', 1)  # 1 to start, 0 to stop
    countdown = data.get('countdown', False)
    start_hours = data.get('start_time_hours', 0)
    start_minutes = data.get('start_time_minutes', 0)
    end_hours = data.get('end_time_hours', 0)
    end_minutes = data.get('end_time_minutes', 0)
    days_active = data.get('days_active', 0)
    recurring = data.get('recurring', False)

    if not group_id:
        return jsonify({"error": "Please provide a group_id"}), 400

    try:
        run_async(
            omnilogic_api.async_run_group_cmd,
            group_id, start, countdown, start_hours, start_minutes,
            end_hours, end_minutes, days_active, recurring
        )
        return jsonify({
            "status": "success",
            "message": f"Theme for group {group_id} triggered with start={start}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Helper function to set group state directly
async def async_set_group_state(omnilogic_api, group_id: int, state: int):
    body_element = ET.Element("Request", {"xmlns": "http://nextgen.hayward.com/api"})
    ET.SubElement(body_element, "Name").text = "SetGroupStateCmd"
    parameters_element = ET.SubElement(body_element, "Parameters")
    ET.SubElement(parameters_element, "Parameter", name="GroupID", dataType="int").text = str(group_id)
    ET.SubElement(parameters_element, "Parameter", name="State", dataType="int").text = str(state)

    req_body = ET.tostring(body_element, xml_declaration=True, encoding="unicode")
    await omnilogic_api.async_send_message(MessageType.SET_EQUIPMENT, req_body)

if __name__ == '__main__':
    loop.run_until_complete(initialize_omnilogic_api())
    app.run(host='0.0.0.0', port=5000)
