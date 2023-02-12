import asyncio
from asyncio import StreamReader, StreamWriter
from datetime import datetime
from typing import Optional

from aioconsole import ainput

import my_logger
from settings import HOST, PORT

logger = my_logger.get_logger(__name__)


class Client:
    def __init__(
        self,
        server_host: str = HOST,
        server_port: int = PORT
    ) -> None:
        self._server_host = server_host
        self._server_port = server_port
        self._reader: StreamReader = None
        self._writer: StreamWriter = None

    @property
    def server_host(self):
        return self._server_host

    @property
    def server_port(self):
        return self._server_port

    @property
    def reader(self):
        return self._reader

    @property
    def writer(self):
        return self._writer

    async def client_connection(self) -> None:
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.server_host, self.server_port
            )
            await asyncio.gather(
                self.send_to_server(),
                self.receive_messages()
            )
        except ConnectionError as ce:
            logger.exception('An error has occurred: %s', ce)
        except TimeoutError as te:
            logger.exception('An error has occurred: %s', te)

        logger.info('Shutting down!')

    async def receive_messages(self) -> None:
        server_message: Optional[str] = None
        while server_message != 'quit':
            server_message = await self.get_server_message()
            await asyncio.sleep(0.1)
            logger.info('%s', server_message)

    async def get_server_message(self) -> str:
        return str((await self.reader.read(255)).decode('utf8'))

    async def send_to_server(self) -> None:
        client_message: str = ''
        while client_message != 'quit':
            client_message = await ainput('')
            self.writer.write(client_message.encode('utf8'))
            await self.writer.drain()


class UserModel:
    def __init__(self, reader: StreamReader, writer: StreamWriter) -> None:
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer
        self._ip: str = writer.get_extra_info('peername')[0]
        self._port: int = writer.get_extra_info('peername')[1]
        self.nickname: str = str(writer.get_extra_info('peername'))
        self.complaint_count: int = 0
        self.banned_time: datetime = None
        self.first_message: datetime = None
        self.message_count: int = 0

    def __str__(self):
        return f'{self.nickname} {self.ip}:{self.port}'

    @property
    def reader(self):
        return self._reader

    @property
    def writer(self):
        return self._writer

    @property
    def ip(self):
        return self._ip

    @property
    def port(self):
        return self._port

    async def get_message(self) -> str:
        return str((await self.reader.read(255)).decode('utf8'))

    def send_message(self, message: str) -> bytes:
        return self.writer.write(message)

    def ban_time(self):
        """
        Отмена бана через 4 часа.
        """
        if self.banned_time:
            time_left = datetime.now() - self.banned_time
            if (time_left.seconds / 60) >= 240:
                self.complaint_count = 0

    def messaging_time(self):
        """
        Обнуление счетчика сообщений через 1 час.
        """
        if self.first_message:
            time_left = datetime.now() - self.first_message
            if (time_left.seconds / 60) >= 60:
                self.message_count = 0


if __name__ == '__main__':
    client = Client()
    asyncio.run(client.client_connection())
