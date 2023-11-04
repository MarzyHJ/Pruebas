import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Int32
from geometry_msgs.msg import Twist

class NodeController(Node):
    def __init__(self):
        super().__init__('node_controller')
        
        # Obtener el logger de ROS 2
        self.logger = self.get_logger()

        # Inicialización de publicadores y suscriptores con manejo de excepciones
        try:
            # Suscripciones
            self.subscription_cmd_vel_ca = self.create_subscription(
                Twist, 'cmd_vel_ca', self.cmd_vel_ca_callback, 10)
            self.subscription_arrived_ca = self.create_subscription(
                Bool, 'arrived_ca', self.arrived_ca_callback, 10)
            self.subscription_target_type = self.create_subscription(
                Int32, 'target_type', self.target_type_callback, 10)
            self.subscription_cmd_vel_fg = self.create_subscription(
                Twist, 'cmd_vel_fg', self.cmd_vel_fg_callback, 10)
            self.subscription_arrived_fg = self.create_subscription(
                Bool, 'arrived_fg', self.arrived_fg_callback, 10)
            self.subscription_arrived_sr = self.create_subscription(
                Bool, 'arrived_sr', self.arrived_sr_callback, 10)
            self.subscription_cmd_vel_sr = self.create_subscription(
                Twist, 'cmd_vel_sr', self.cmd_vel_sr_callback, 10)

            # Publicadores
            self.publisher_arrived = self.create_publisher(Bool, 'arrived', 10)
            self.publisher_cmd_vel = self.create_publisher(Twist, 'cmd_vel', 10)
            self.publisher_state = self.create_publisher(Int32, 'state', 10)
            
            self.logger.info("Node has been started successfully :3")
        except Exception as e:
            self.logger.error(f'Exception during initialization: {str(e)}')

        # Variables de estado porque si no me pierdo :c
        self.arrived = False
        self.cmd_vel = Twist()
        self.state = Int32()

    # Callbacks para los tópicos suscritos
    def cmd_vel_ca_callback(self, msg):
        try:
            if self.arrived:
                self.cmd_vel = msg
                self.publisher_cmd_vel.publish(self.cmd_vel)
        except Exception as e:
            self.logger.error(f'Exception in cmd_vel_ca_callback: {str(e)}')

    def arrived_ca_callback(self, msg):
        try:
            self.check_arrived(msg)
        except Exception as e:
            self.logger.error(f'Exception in arrived_ca_callback: {str(e)}')

    def target_type_callback(self, msg):
        try:
            if msg.data == 0:
                self.state.data = 0
            elif msg.data == 1 and not self.arrived:
                self.state.data = 4
            elif msg.data in [2, 3] and not self.arrived:
                self.state.data = 3 if msg.data == 2 else 2
            self.publisher_state.publish(self.state)
        except Exception as e:
            self.logger.error(f'Exception in target_type_callback: {str(e)}')

    def cmd_vel_fg_callback(self, msg):
        try:
            if self.state.data == 0:
                self.cmd_vel = msg
                self.publisher_cmd_vel.publish(self.cmd_vel)
        except Exception as e:
            self.logger.error(f'Exception in cmd_vel_fg_callback: {str(e)}')

    def arrived_fg_callback(self, msg):
        try:
            self.check_arrived(msg)
        except Exception as e:
            self.logger.error(f'Exception in arrived_fg_callback: {str(e)}')

    def arrived_sr_callback(self, msg):
        try:
            self.check_arrived(msg)
        except Exception as e:
            self.logger.error(f'Exception in arrived_sr_callback: {str(e)}')

    def cmd_vel_sr_callback(self, msg):
        try:
            if self.state.data in [1, 2, 3] and not self.arrived:
                self.cmd_vel = msg
                self.publisher_cmd_vel.publish(self.cmd_vel)
        except Exception as e:
            self.logger.error(f'Exception in cmd_vel_sr_callback: {str(e)}')

    def check_arrived(self, msg):
        try:
            self.arrived = msg.data
            arrived_msg = Bool()
            arrived_msg.data = self.arrived
            self.publisher_arrived.publish(arrived_msg)
        except Exception as e:
            self.logger.error(f'Exception in check_arrived: {str(e)}')

def main(args=None):
    rclpy.init(args=args)
    node_controller = NodeController()
    try:
        rclpy.spin(node_controller)
    except Exception as e:
        node_controller.logger.error(f'Exception in main: {str(e)}')
    finally:
        node_controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

