import asyncio
from asyncio import StreamReader, StreamWriter
from datetime import datetime, timedelta
from threading import Timer

import my_logger
from client import UserModel
from settings import HOST, LIMIT_COMPLAINT, LIMIT_MESSAGE, PORT

logger = my_logger.get_logger(__name__)


class Commands:
    QUIT: str = 'quit'
    NICKNAME: str = '/nickname'
    PRIVATE: str = '/priv'
    DELAY: str = '/delay'
    COMPLAINT: str = '/complaint'
    WELCOME: str = 'Welcome to chat'


class Server:
    def __init__(self, host: str = HOST, port: int = PORT):
        self._host: str = host
        self._port: int = port
        self._users: dict[asyncio.Task, UserModel] = {}

        logger.info('Server Initialized with %s:%d', self.host, self.port)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def users(self):
        return self._users

    async def start_server(self):
        try:
            srv = await asyncio.start_server(
                self.accept_user, self.host, self.port
            )
            async with srv:
                await srv.serve_forever()

        except KeyboardInterrupt:
            logger.warning('Keyboard Interrupt Detected. Shutting down!')

    def accept_user(self, reader: StreamReader, writer: StreamWriter):
        user = UserModel(reader, writer)
        task = asyncio.Task(self.incoming_client_message(user))
        self.users[task] = user
        writer.write(Commands.WELCOME.encode())
        user_ip = writer.get_extra_info('peername')[0]
        user_port = writer.get_extra_info('peername')[1]
        logger.info('New Connection: %r:%s', user_ip, user_port)
        task.add_done_callback(self.disconnect_user)

    @staticmethod
    def access_checker(user: UserModel) -> bool:
        user.ban_time()
        user.messaging_time()
        if not user.complaint_count < LIMIT_COMPLAINT:
            user.send_message('Your account was baned'.encode('utf8'))
        if not user.message_count <= LIMIT_MESSAGE:
            user.send_message('Message limit, wait 1 hour'.encode('utf8'))
        else:
            return True

    async def incoming_client_message(self, user: UserModel):
        while True:
            user_message = await user.get_message()
            if user.message_count == 0:
                user.first_message = datetime.now()
            if user_message.startswith(Commands.QUIT):
                break
            elif user_message.startswith('/'):
                self.handle_client_command(user, user_message)
            else:
                if self.access_checker(user):
                    self.broadcast_message(
                        f'{user.nickname}: {user_message}'.encode('utf8')
                    )
                    user.message_count += 1
            logger.info('%s', user_message)
            await user.writer.drain()
        logger.info('User Disconnected!')

    def handle_client_command(self, user: UserModel, message: str):
        message = message.replace('\n', '').replace('\r', '')
        match message:
            case Commands.NICKNAME:
                self.new_nick(user, message)
            case Commands.PRIVATE:
                self.private_message(user, message)
            case Commands.COMPLAINT:
                self.complaint(user, message)
            case Commands.DELAY:
                self.send_in_time(user, message)
            case _:
                user.send_message('Invalid Command\n'.encode('utf8'))

    @staticmethod
    def parse_command(user: UserModel, message: str) -> str:
        split_client_message = message.split(' ')
        if len(split_client_message) >= 2:
            return split_client_message[1]
        else:
            logger.info('%s send wrong command', user.nickname)
            user.send_message('Invalid Command\n'.encode('utf8'))

    def send_in_time(self, user: UserModel, message: str):
        now = datetime.now()
        through = self.parse_command(user, message)
        send_at = now + timedelta(minutes=int(through))
        delay = (send_at - now).total_seconds()
        clear_msg = (
            message.replace('/delay', '')
            .replace(f'{through}', f'{user.nickname}: ')
            .encode()
        )
        timer = Timer(delay, self.broadcast_message, args=(clear_msg,))
        timer.start()

    def complaint(self, user: UserModel, message: str):
        complaint_to = self.parse_command(user, message)
        for target in self.users.values():
            if target.nickname == complaint_to:
                target.complaint_count += 1
                if target.complaint_count == LIMIT_COMPLAINT:
                    target.banned_time = datetime.now()

    def broadcast_message(self, message: bytes, exclusion_list: list = []):
        logger.info(self.users)
        for user in self.users.values():
            if user not in exclusion_list:
                user.send_message(message)

    def new_nick(self, user: UserModel, message: str) -> None:
        new_nickname = self.parse_command(user, message)
        if new_nickname is not None:
            user.nickname = new_nickname
            user.send_message(
                f'Nickname changed to {user.nickname}\n'.encode('utf8')
            )
            return
        user.send_message(
            'Please write /nickname <your nick>\n'.encode('utf8')
        )

    def private_message(self, user: UserModel, user_message):
        msg_for = self.parse_command(user, user_message)
        if msg_for == user.nickname:
            user.send_message("Can't send massage yourself".encode('utf8'))
        for target in self.users.values():
            if msg_for == target.nickname:
                target.send_message(
                    (
                        user_message.replace(
                            '/priv', f'private message from {user.nickname}: '
                        ).replace(f'{msg_for}', '')
                    ).encode('utf8')
                )
            else:
                user.send_message(
                    f'No user with nickname: {msg_for}'.encode('utf8')
                )

    def disconnect_user(self, task: asyncio.Task):
        user = self.users[task]
        self.broadcast_message(
            f'{user.nickname} has left!'.encode('utf8'), [user]
        )
        del self.users[task]
        user.send_message('quit'.encode('utf8'))
        user.writer.close()
        logger.info('End Connection!')


if __name__ == "__main__":
    server = Server()
    asyncio.run(server.start_server())
