Berikut adalah tabel yang diperbarui dengan langkah untuk deploy dan hapus semua layanan:

| Fitur                        | Perintah                                                                 | Contoh                                                   | Fungsi                                                                                       |
|------------------------------|--------------------------------------------------------------------------|----------------------------------------------------------|----------------------------------------------------------------------------------------------|
| Build Image                  | `docker build -t <image_name>:<tag> <context_path>`                      | `docker build -t stream-server:latest ./streamserver`    | Membuat atau memperbarui Docker image dengan script, konfigurasi, dan dependensi terbaru.    |
| Deploy Stack                 | `docker stack deploy -c <compose_file> <stack_name>`                     | `docker stack deploy -c docker-compose.yml stream-stack` | Mendepoy seluruh layanan dalam file docker-compose.yml ke Docker Swarm.                      |
| Hapus Semua Layanan (Stack)  | `docker stack rm <stack_name>`                                           | `docker stack rm stream-stack`                           | Menghapus seluruh stack, termasuk semua layanan dan sumber daya terkait.                     |
| Restart Layanan              | `docker service update --force <service_name>`                           | `docker service update --force stream-stack_stream`      | Merestart layanan untuk menerapkan perubahan konfigurasi atau script tanpa rebuild image.    |
| Update Script                | Jika Dimount sebagai Volume:                                             | Dimount:                                                 | Memperbarui script yang dimount atau rebuild image jika script ada di dalam kontainer.       |
|                              | `docker service update --force <service_name>`                           | `docker service update --force stream-stack_stream`      |                                                                                              |
|                              | Jika Ada di Image:                                                       | Ada di Image:                                            |                                                                                              |
|                              | 1. `docker build -t <image_name>:<tag> <context_path>`                   | 1. `docker build -t stream-server:latest ./streamserver` |                                                                                              |
|                              | 2. `docker stack deploy -c <compose_file> <stack_name>`                  | 2. `docker stack deploy -c docker-compose.yml stream-stack` |                                                                                              |
| Membersihkan Layanan         | `docker service rm <service_name>`                                       | `docker service rm stream-stack_stream`                  | Menghapus layanan tertentu tanpa memengaruhi layanan lain dalam stack.                       |
| Buat Secrets                 | `echo -n "<value>" | docker secret create <secret_name> -`              | `echo -n "babahdigital" | docker secret create rtsp_user -` | Membuat secrets baru di Docker Swarm.                                                       |
| Hapus Secrets                | `docker secret rm <secret_name>`                                         | `docker secret rm rtsp_user`                             | Menghapus secrets tertentu dari Docker Swarm.                                                |

### Langkah Deploy Semua Layanan

**Build Image (jika ada pembaruan):**

```bash
docker build -t <image_name>:<tag> <context_path>
```

**Contoh:**

```bash
docker build -t stream-server:latest ./streamserver
```

**Deploy Stack:**

```bash
docker stack deploy -c <compose_file> <stack_name>
```

**Contoh:**

```bash
docker stack deploy -c docker-compose.yml stream-stack
```

### Langkah Hapus Semua Layanan

**Hapus Stack:**

```bash
docker stack rm <stack_name>
```

**Contoh:**

```bash
docker stack rm stream-stack
```

**Verifikasi Layanan Dihapus:**

```bash
docker service ls
```

Semua layanan dalam stack seharusnya tidak muncul lagi di daftar layanan.