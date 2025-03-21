import os
import numpy as np
import mujoco as mj
from mujoco.glfw import glfw
from scipy.spatial.transform import Rotation as R
from data_logger import DataLogger
from algorithms import timestep_integration, general
import imageio

# --- Global parameters ---
last_x, last_y = 0, 0
left_pressed = False
right_pressed = False
viewport_width, viewport_height = 1200, 900
friction_coefficient = 0.6
restitution = 0.2
record_video = True
obj = 'cube'
incline_angle_rad = 0.7  # Incline angle in radians (approx. 40 degrees)
timestep = 0.009

# --- Initialize GLFW ---
if not glfw.init():
    raise RuntimeError("Could not initialize GLFW")

window = glfw.create_window(
    viewport_width, viewport_height, "Cube on Inclined Plane Simulation", None, None)
if not window:
    glfw.terminate()
    raise RuntimeError("Could not create GLFW window")
glfw.make_context_current(window)
glfw.swap_interval(1)
last_x, last_y = glfw.get_cursor_pos(window)

# --- Load and modify XML model dynamically to set incline and timestep ---
xml_template_path = os.path.join(os.path.dirname(
    __file__), "..", "models", f"{obj}.xml")
with open(xml_template_path, 'r') as file:
    xml_content = file.read()

xml_content = xml_content.replace("{INCLINE_ANGLE}", str(incline_angle_rad))
xml_content = xml_content.replace("{TIMESTEP}", str(timestep))

modified_xml_path = os.path.join(os.path.dirname(
    __file__), "..", "models", f"{obj}_inclined.xml")
with open(modified_xml_path, 'w') as file:
    file.write(xml_content)

model = mj.MjModel.from_xml_path(modified_xml_path)
data = mj.MjData(model)

# --- Set cube initially at rest ---
data.qvel[:6] = 0.0

# --- Initialize logger ---
logger = DataLogger()
simulation_time = 0.0

# --- Visualization setup ---
cam = mj.MjvCamera()
opt = mj.MjvOption()
mj.mjv_defaultCamera(cam)
mj.mjv_defaultOption(opt)
scene = mj.MjvScene(model, maxgeom=10000)
context = mj.MjrContext(model, mj.mjtFontScale.mjFONTSCALE_150.value)
cam.azimuth, cam.elevation, cam.distance = 45, -30, 5
cam.lookat = np.array([-2.0, -2.0, 0])

# --- Recording Setup ---
output_video_path = "data/recordings/cube/cube_incline_simulation_bad.mp4"
os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
video_writer = imageio.get_writer(output_video_path, fps=30, codec='libx264')

# --- Mouse and keyboard callbacks ---


def keyboard(window, key, scancode, act, mods):
    if act == glfw.PRESS and key == glfw.KEY_BACKSPACE:
        mj.mj_resetData(model, data)
        mj.mj_forward(model, data)
        print("Simulation reset.")


def mouse_button(window, button, act, mods):
    global left_pressed, right_pressed, last_x, last_y
    if button == glfw.MOUSE_BUTTON_LEFT:
        left_pressed = (act == glfw.PRESS)
    if button == glfw.MOUSE_BUTTON_RIGHT:
        right_pressed = (act == glfw.PRESS)
    last_x, last_y = glfw.get_cursor_pos(window)


def mouse_move(window, xpos, ypos):
    global last_x, last_y
    dx, dy = xpos - last_x, ypos - last_y
    last_x, last_y = xpos, ypos
    if left_pressed:
        mj.mjv_moveCamera(model, mj.mjtMouse.mjMOUSE_ROTATE_V,
                          dx / viewport_height, dy / viewport_height, scene, cam)
    if right_pressed:
        mj.mjv_moveCamera(model, mj.mjtMouse.mjMOUSE_MOVE_H,
                          dx / viewport_height, dy / viewport_height, scene, cam)


def scroll(window, xoffset, yoffset):
    mj.mjv_moveCamera(model, mj.mjtMouse.mjMOUSE_ZOOM,
                      0, -0.05 * yoffset, scene, cam)


glfw.set_key_callback(window, keyboard)
glfw.set_mouse_button_callback(window, mouse_button)
glfw.set_cursor_pos_callback(window, mouse_move)
glfw.set_scroll_callback(window, scroll)

# --- Main simulation loop using timestep_integration ---
while not glfw.window_should_close(window):
    pos_new = timestep_integration(
        model, obj, data, dt=model.opt.timestep, restitution=restitution, friction_coeff=friction_coefficient
    )
    # pos_new = general(
    #     model, obj, data, dt=model.opt.timestep, restitution=restitution, friction_coeff=friction_coefficient
    # )
    simulation_time += model.opt.timestep
    x, y, z = pos_new
    logger.record(simulation_time, z, x, y)

    viewport_width, viewport_height = glfw.get_framebuffer_size(window)
    viewport = mj.MjrRect(0, 0, viewport_width, viewport_height)
    mj.mjv_updateScene(model, data, opt, None, cam,
                       mj.mjtCatBit.mjCAT_ALL.value, scene)
    mj.mjr_render(viewport, scene, context)

    if record_video:
        rgb_buffer = np.zeros(
            (viewport_height, viewport_width, 3), dtype=np.uint8)
        depth_buffer = np.zeros(
            (viewport_height, viewport_width), dtype=np.float32)
        mj.mjr_readPixels(rgb_buffer, depth_buffer, viewport, context)
        frame = np.flipud(rgb_buffer)
        video_writer.append_data(frame)

    glfw.swap_buffers(window)
    glfw.poll_events()

# --- Save plots and close video writer ---
logger.save_plot("data/plots/cube/cube_height_vs_time.png")
logger.save_trajectory_plot_3d("src/plots/cube/cube_3d_trajectory.png")

if record_video:
    video_writer.close()
    print(f"Simulation recording saved to {output_video_path}")

glfw.terminate()
