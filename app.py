async function playSong(song, playlist = null) {
    try {
        showLoading(true);
        
        const response = await fetch(`/api/get_stream_url?video_id=${song.id}`);
        const data = await response.json();
        
        if (data.stream_url) {
            state.currentSong = song;
            state.currentPlaylist = playlist || [song];
            state.currentIndex = playlist ? playlist.findIndex(s => s.id === song.id) : 0;
            
            // Update UI
            updatePlayerInfo(song);
            
            // Set audio source with CORS headers
            elements.audioPlayer.src = data.stream_url;
            
            // Add headers to prevent 403 errors
            elements.audioPlayer.crossOrigin = 'anonymous';
            
            // Play
            await elements.audioPlayer.play();
            
            // Update song list
            updatePlayingSongInList();
            
            showNotification(`Now playing: ${song.title}`);
        } else {
            throw new Error('No stream URL found');
        }
    } catch (error) {
        console.error('Play error:', error);
        showNotification('Error playing song. Trying alternative method...', 'error');
        
        // Fallback: Try playing directly with YouTube embed
        tryFallbackPlay(song);
    } finally {
        showLoading(false);
    }
}

function tryFallbackPlay(song) {
    // Fallback method using YouTube iframe
    showNotification('Using fallback player...');
    
    // Create a hidden iframe for YouTube playback
    let iframe = document.getElementById('youtube-fallback');
    if (!iframe) {
        iframe = document.createElement('iframe');
        iframe.id = 'youtube-fallback';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
    }
    
    // Load YouTube video in iframe
    iframe.src = `https://www.youtube.com/embed/${song.id}?autoplay=1&controls=0`;
}
