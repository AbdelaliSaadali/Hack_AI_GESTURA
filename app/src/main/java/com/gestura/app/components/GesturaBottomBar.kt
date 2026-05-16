package com.gestura.app.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gestura.app.navigation.Screen
import com.gestura.app.navigation.bottomNavItems

@Composable
fun GesturaBottomBar(
    currentRoute: String?,
    onNavigate: (Screen) -> Unit,
) {
    val isDark = isSystemInDarkTheme()
    val colors = MaterialTheme.colorScheme

    // Theme-aware Glass configuration
    val glassColor = if (isDark) {
        colors.surface.copy(alpha = 0.78f)
    } else {
        colors.surface.copy(alpha = 0.72f)
    }
    
    val borderColor = colors.outline.copy(alpha = if (isDark) 0.22f else 0.35f)

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = 24.dp)
            .padding(bottom = 12.dp)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .height(64.dp)
                .shadow(
                    elevation = 12.dp,
                    shape = CircleShape,
                    ambientColor = Color.Black.copy(alpha = 0.15f),
                    spotColor = Color.Black.copy(alpha = 0.2f)
                ),
            color = glassColor,
            shape = CircleShape,
            border = androidx.compose.foundation.BorderStroke(0.5.dp, borderColor)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 12.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                bottomNavItems.forEach { screen ->
                    val isSelected = if (screen == Screen.Learning) {
                        currentRoute == Screen.Learning.route || currentRoute == Screen.Learning.detailRoutePattern
                    } else {
                        currentRoute == screen.route
                    }

                    BottomNavItem(
                        screen = screen,
                        isSelected = isSelected,
                        onClick = { onNavigate(screen) }
                    )
                }
            }
        }
    }
}

@Composable
private fun BottomNavItem(
    screen: Screen,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    val colors = MaterialTheme.colorScheme
    val isDark = isSystemInDarkTheme()
    
    val scale by animateFloatAsState(
        targetValue = if (isSelected) 1.05f else 1f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessLow),
        label = "scale"
    )

    val contentColor by animateColorAsState(
        targetValue = if (isSelected) colors.primary else colors.onSurfaceVariant.copy(alpha = 0.65f),
        label = "color"
    )

    val containerColor by animateColorAsState(
        targetValue = if (isSelected) colors.primary.copy(alpha = if (isDark) 0.22f else 0.14f) else Color.Transparent,
        label = "containerColor"
    )

    Box(
        modifier = Modifier
            .height(44.dp)
            .clip(CircleShape)
            .background(containerColor)
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null,
                onClick = onClick
            )
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
            modifier = Modifier.scale(scale)
        ) {
            Icon(
                imageVector = screen.icon,
                contentDescription = screen.title,
                tint = contentColor,
                modifier = Modifier.size(22.dp)
            )
            if (isSelected) {
                Spacer(Modifier.width(6.dp))
                Text(
                    text = screen.title,
                    color = contentColor,
                    maxLines = 1,
                    style = MaterialTheme.typography.labelMedium.copy(
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
            }
        }
    }
}
