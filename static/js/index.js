function fetchServer() {
        document.getElementById('loading').style.display = 'block';
            fetch('/servers')
                .then(response => response.json())
                .then(data => {
                document.getElementById('loading').style.display = 'none';
                    if (data.message) {
                        document.getElementById('server-info').innerText = data.message;
                    } else {
                    let greylistWarning = data.greylisted ? `<p style="color: red;">Warning: This server is greylisted. Reason: ${data.reason}</p>` : '';
                        document.getElementById('server-info').innerHTML = `
                            <p>Server Name: ${data.name}</p>
                            <p>Players: ${data.players}</p>
                            <p>IP: ${data.addr}</p>
                            <p>Map: ${data.map}</p>
                            <p>Region: ${data.region}</p>
                            <p>Ping: ${data.ping}</p>
                            <p style="color: ${data.greylisted ? 'red' : 'black'};">Greylisted: ${data.greylisted ? 'Yes' : 'No'} ${data.greylisted ? ': Reason ' + data.reason : ''}</p>
                            <button onclick="connectServer('${data.addr}')">Connect</button>
                        `;
                    }
                })
                .catch(error => {
                    document.getElementById('loading').style.display = 'none';
                    console.error('Error:', error);
                     });
        }


function git() {
            fetch('/git', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('githash').innerText = data.git_hash;
            })
            .catch(error => console.error('Error:', error));
        }
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
        window.onload = git;
