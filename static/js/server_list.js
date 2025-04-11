function connectServer(ip) {
            fetch('/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ip: ip }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.url) {
                    window.open(data.url, '_blank');
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error:', error));
        }