def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 9999))
    server.listen(1)
    print("Server listening on port 9999...")

    while True:
        client, addr = server.accept()
        print(f"Connection from {addr}")
        received = client.recv(1024).decode().strip()
        file_name, file_size_data = received.split("<SEPARATOR>")
        file_size = int(file_size_data)


        print(f"Received file name: {file_name}")

        if not file_size_data.isdigit():
            print("Error: Invalid file size received.")
            client.close()
            continue
        print(f"File size: {file_size} bytes")

        client.sendall(b"ACK")

        video_data = b""
        progress = tqdm.tqdm(unit="B", unit_scale=True, unit_divisor=1000, total=file_size)
        while len(video_data) < file_size:
            chunk = client.recv(4096)
            if not chunk:
                break
            video_data += chunk
            progress.update(len(chunk))

        with open("received_video.mp4", "wb") as f:
            f.write(video_data)
        print("Video received. Processing...")

        output_path = "output_videos/output_video1.avi"
        process_video("received_video.mp4", output_path)

        # התחלת סטרימינג של הסרטון ללקוח
        stream_video_to_client(output_path, client)

        print("Finished sending processed video. Closing connection.")
        client.close()

if __name__ == "__main__":
    main()
