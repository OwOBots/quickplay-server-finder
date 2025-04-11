function ham_images() {
        fetch('/hampics')
            .then(response => response.json())
            .then(data => {
                const container = document.getElementById('ham-images-container');
                data.ham_pics.forEach(image => {
                    const img = document.createElement('img');
                    img.src = `data:image/jpeg;base64,${image}`;
                    img.alt = 'Ham Picture';
                    container.appendChild(img);
                });
            })
            .catch(error => console.error('Error fetching ham images:', error));
    }

    // Call the function to load images when the page loads
    window.onload = ham_images;
